import app
import boto3
import hashlib
import io
import magic
import os
import requests

from botocore.exceptions import ClientError
from cloudevents.conversion import to_dict
from cloudevents.http import CloudEvent
from elody.exceptions import (
    DuplicateFileException,
    FileNotFoundException,
    NotFoundException,
)
from elody.util import get_mimetype_from_filename
from humanfriendly import parse_size
from PIL import Image, ExifTags, TiffImagePlugin


class S3StorageManager:
    def __init__(self):
        self.s3 = boto3.resource(
            "s3",
            endpoint_url=os.getenv("MINIO_ENDPOINT"),
            aws_access_key_id=os.getenv("MINIO_ACCESS_KEY"),
            aws_secret_access_key=os.getenv("MINIO_SECRET_KEY"),
        )
        self.collection_api_url = os.getenv("COLLECTION_API_URL")
        self.storage_api_url = os.getenv("STORAGE_API_URL")
        self.headers = None
        self.session = requests.Session()

    def set_headers(self, headers):
        self.headers = headers
        self.session.headers.pop("Authorization", None)
        self.session.headers.pop("apikey", None)
        self.session.headers.update(headers)

    def __calculate_md5(self, file):
        hash_obj = hashlib.md5()
        while chunk := file.read(parse_size("8 KiB")):
            hash_obj.update(chunk)
        file.seek(0)
        return hash_obj.hexdigest()

    def __get_exif_for_mediafile(self, mediafile):
        artist = f'source: {self.__get_item_metadata_value(mediafile, "source")}'
        if photographer := self.__get_item_metadata_value(mediafile, "photographer"):
            artist = f"photographer: {photographer}, {artist}"
        rights = f'license: {self.__get_item_metadata_value(mediafile, "rights")}'
        if copyrights := self.__get_item_metadata_value(mediafile, "copyright"):
            rights = f"rightsholder: {copyrights}, {rights}"
        return artist, rights

    def __get_file_mimetype(self, file, key):
        file.seek(0)
        mime = magic.Magic(mime=True).from_buffer(file.read(parse_size("8 KiB")))
        file.seek(0)
        if mime == "application/octet-stream":
            mime = get_mimetype_from_filename(key)
        return mime

    def __get_item_metadata_value(self, item, key):
        for entry in item["metadata"]:
            if entry["key"] == key:
                return entry["value"]
        return False

    def __get_raw_id(self, item):
        return item.get("_key", item["_id"])

    def __handle_duplicate_file(self, mediafile, mimetype, md5sum, filename, message):
        try:
            found_mediafile = self._get_mediafile(md5sum)
        except NotFoundException:
            self.__update_mediafile_information(mediafile, md5sum, filename, mimetype)
            message = (
                f"{message} No existing mediafile for file found, not deleting new one."
            )
            raise DuplicateFileException(message)
        mediafile_id = self.__get_raw_id(mediafile)
        if self.__get_raw_id(found_mediafile) != mediafile_id:
            self.session.delete(f"{self.collection_api_url}/mediafiles/{mediafile_id}")
            message = f"{message} Existing mediafile for file found, deleting new one."
        if self.is_metadata_updated(found_mediafile, mediafile):
            message = f"{message} Metadata not up-to-date, updating."
            payload = {"metadata": mediafile.get("metadata", [])}
            self.session.patch(
                f"{self.collection_api_url}/mediafiles/{md5sum}", json=payload
            )
        raise DuplicateFileException(message)

    def __signal_file_uploaded(self, mediafile, mimetype, url, headers):
        attributes = {"type": "dams.file_uploaded", "source": "dams"}
        data = {
            "mediafile": mediafile,
            "mimetype": mimetype,
            "url": url,
            "headers": headers,
        }
        event = to_dict(CloudEvent(attributes, data))
        app.rabbit.send(event, routing_key="dams.file_uploaded")

    def __update_mediafile_information(
        self, mediafile, md5sum, new_key, mimetype, exif_data=None
    ):
        new_key = new_key.split("/")[-1]
        mediafile["identifiers"].append(md5sum)
        mediafile["original_filename"] = mediafile["filename"]
        mediafile["filename"] = new_key
        mediafile["original_file_location"] = f"/download/{new_key}"
        mediafile["thumbnail_file_location"] = (
            f"/iiif/3/{new_key}/full/,150/0/default.jpg"
        )
        mediafile["mimetype"] = mimetype
        if exif_data:
            mediafile["technical_metadata"] = exif_data
        self.session.put(
            f"{self.collection_api_url}/mediafiles/{self.__get_raw_id(mediafile)}",
            json=mediafile,
        )

    def _get_mediafile(self, mediafile_id, fatal=True):
        req = self.session.get(f"{self.collection_api_url}/mediafiles/{mediafile_id}")
        if req.status_code == 200:
            return req.json()
        elif not fatal:
            return None
        elif req.status_code == 404:
            raise NotFoundException("Could not get mediafile with provided id")
        else:
            raise Exception("Something went wrong while getting mediafile")

    def add_exif_data(self, mediafile):
        if "image" not in mediafile["mimetype"]:
            return
        image = self.download_file(mediafile["filename"])["stream"]
        img = Image.open(image)
        exif = img.getexif()
        exif[0x013B], exif[0x8298] = self.__get_exif_for_mediafile(mediafile)
        buf = io.BytesIO()
        img.save(buf, img.format, exif=exif)
        buf.seek(0)
        self.s3.Bucket(self.__get_bucket_name()).upload_fileobj(
            Fileobj=buf, Key=self.__get_key(mediafile["filename"])
        )
        self.session.patch(
            f'{self.collection_api_url}/mediafiles/{mediafile["identifiers"][0]}',
            json={"exif": str(exif)},
        )

    def check_file_exists(self, filename, md5sum, ticket=None):
        bucket_name = self.__get_bucket_name(ticket)
        client = self.s3.Bucket(bucket_name).meta.client
        if ticket:
            try:
                client.head_object(Bucket=bucket_name, Key=ticket["location"])
            except ClientError as ex:
                if ex.response["Error"]["Code"] == "404":
                    return
            raise DuplicateFileException(
                f'{ticket["location"]} already exists in {bucket_name}'
            )
        else:
            objects = client.list_objects_v2(Bucket=bucket_name, Prefix=md5sum)
            if len(objects.get("Contents", [])):
                existing_file = objects.get("Contents", [])[0]["Key"]
                error_message = (
                    f"Duplicate file {filename} matches existing file {existing_file}."
                )
                raise DuplicateFileException(error_message, existing_file, md5sum)

    def check_health(self):
        self.s3.buckets.all()
        return True

    def delete_files(self, files):
        payload = {"Objects": [{"Key": file} for file in files], "Quiet": True}
        self.s3.Bucket(self.__get_bucket_name()).delete_objects(Delete=payload)

    def download_file(self, file_name, range=None, ticket=None):
        bucket_name = self.__get_bucket_name(ticket)
        client = self.s3.Bucket(bucket_name).meta.client
        try:
            if range:
                file_obj = client.get_object(
                    Bucket=bucket_name,
                    Key=self.__get_key(file_name, ticket=ticket),
                    Range=range,
                )
            else:
                file_obj = client.get_object(
                    Bucket=bucket_name, Key=self.__get_key(file_name, ticket=ticket)
                )
        except ClientError:
            message = f"File {file_name} not found with key {self.__get_key(file_name, ticket=ticket)}"
            app.logger.error(message)
            raise FileNotFoundException(message)
        return {"stream": file_obj["Body"], "content_length": file_obj["ContentLength"]}

    def get_file_info(self, file_name, ticket=None):
        content_type = get_mimetype_from_filename(file_name)
        if ticket:
            bucket_name = self.__get_bucket_name(ticket)
            client = self.s3.Bucket(bucket_name).meta.client
            file_info = client.head_object(
                Bucket=bucket_name, Key=self.__get_key(file_name, ticket=ticket)
            )
            file_info["ContentType"] = content_type
            return file_info
        return {"ContentType": content_type}

    def get_stream_generator(self, stream):
        return stream.iter_chunks()

    def is_metadata_updated(self, old_mediafile, new_mediafile):
        old_metadata = old_mediafile.get("metadata", [])
        new_metadata = new_mediafile.get("metadata", [])
        if len(old_metadata) != len(new_metadata):
            return True
        unmatched = list(old_metadata)
        for item in new_metadata:
            try:
                unmatched.remove(item)
            except ValueError:
                return True
        return len(unmatched) > 0

    def __get_bucket_name(self, ticket=None):
        if ticket:
            return ticket["bucket"]
        if bucket := os.getenv("MINIO_BUCKET"):
            return bucket
        raise Exception("No bucket for upload was specified")

    def __get_key(self, key, md5sum=None, ticket=None, transcode=False):
        input_key = ticket["location"] if ticket else key
        split_key = input_key.split("/")
        if transcode:
            split_key[-1] = f"transcode-{split_key[-1]}"
        if md5sum:
            split_key[-1] = f"{md5sum}-{split_key[-1]}"
        return "/".join(split_key)

    def _get_exif_data(self, file):
        image = Image.open(file)
        exif_data = image.getexif()._get_merged_dict()
        file.seek(0)
        data = []
        if exif_data is None:
            return None
        for key, value in exif_data.items():
            if key in ExifTags.TAGS:
                value = self._handle_value_to_be_serializable(value)
                data.append({"key": ExifTags.TAGS[key], "value": value})
        return data

    def _handle_value_to_be_serializable(self, value):
        if isinstance(value, TiffImagePlugin.IFDRational):
            return str(value)
        elif isinstance(value, bytes):
            return value.decode("utf-8", "ignore")
        elif isinstance(value, (tuple, list)):
            return [self._handle_value_to_be_serializable(v) for v in value]
        else:
            return value

    def upload_file(self, file, mediafile_id, key, ticket):
        mediafile = self._get_mediafile(mediafile_id, fatal=ticket is None)
        md5sum = self.__calculate_md5(file)
        mimetype = self.__get_file_mimetype(file, key)
        exif_data = (
            self._get_exif_data(file) if mimetype.startswith("image") else list()
        )
        try:
            self.check_file_exists(key, md5sum, ticket)
        except DuplicateFileException as ex:
            if mediafile:
                self.__handle_duplicate_file(
                    mediafile, mimetype, ex.md5sum, ex.filename, ex.message
                )
        key = self.__get_key(key, md5sum=md5sum, ticket=ticket)
        self.s3.Bucket(self.__get_bucket_name(ticket)).upload_fileobj(
            Fileobj=file, Key=key
        )
        if mediafile:
            self.__update_mediafile_information(
                mediafile, md5sum, key, mimetype, exif_data
            )
            self.__signal_file_uploaded(
                mediafile,
                mimetype,
                f'{self.storage_api_url}{mediafile["original_file_location"]}',
                self.headers,
            )

    def upload_transcode(self, file, mediafile_id, key, ticket):
        mediafile = self._get_mediafile(mediafile_id)
        md5sum = self.__calculate_md5(file)
        key = self.__get_key(key, md5sum=md5sum, transcode=True, ticket=ticket)
        self.check_file_exists(key, md5sum)
        self.s3.Bucket(self.__get_bucket_name(ticket)).upload_fileobj(
            Fileobj=file, Key=key
        )
        mediafile["identifiers"].append(md5sum)
        new_key = key.split("/")[-1]
        data = {
            "filename": key,
            "transcode_file_location": f"/download/{new_key}",
            "thumbnail_file_location": f"/iiif/3/{new_key}/full/,150/0/default.jpg",
        }
        try:
            self.session.post(
                f"{self.collection_api_url}/mediafiles/{mediafile_id}/derivatives",
                json=data,
            )
        except Exception as ex:
            raise Exception(str(ex))
