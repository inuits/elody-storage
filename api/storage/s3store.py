import app
import boto3
import hashlib
import io
import magic
import mimetypes
import os
import requests

from botocore.exceptions import ClientError
from cloudevents.conversion import to_dict
from cloudevents.http import CloudEvent
from exceptions import DuplicateFileException, MediafileNotFoundException
from humanfriendly import parse_size
from PIL import Image


class S3StorageManager:
    def __init__(self):
        self.s3 = boto3.resource(
            "s3",
            endpoint_url=os.getenv("MINIO_ENDPOINT"),
            aws_access_key_id=os.getenv("MINIO_ACCESS_KEY"),
            aws_secret_access_key=os.getenv("MINIO_SECRET_KEY"),
        )
        self.bucket_name = os.getenv("MINIO_BUCKET")
        self.bucket = self.s3.Bucket(self.bucket_name)
        self.client = self.bucket.meta.client
        self.collection_api_url = os.getenv("COLLECTION_API_URL")
        self.storage_api_url = os.getenv("STORAGE_API_URL")
        self.headers = {"Authorization": f'Bearer {os.getenv("STATIC_JWT", "None")}'}

    def check_file_exists(self, filename, md5sum):
        objects = self.client.list_objects_v2(Bucket=self.bucket_name, Prefix=md5sum)
        if len(objects.get("Contents", [])):
            existing_file = objects.get("Contents", [])[0]["Key"]
            error_message = (
                f"Duplicate file {filename} matches existing file {existing_file}."
            )
            raise DuplicateFileException(error_message, existing_file, md5sum)

    def __calculate_md5(self, file):
        hash_obj = hashlib.md5()
        while chunk := file.read(parse_size("8 KiB")):
            hash_obj.update(chunk)
        file.seek(0, 0)
        return hash_obj.hexdigest()

    def _update_mediafile_information(
        self, mediafile, md5sum, new_key, mediafile_id, mimetype
    ):
        mediafile["identifiers"].append(md5sum)
        mediafile["original_filename"] = mediafile["filename"]
        mediafile["filename"] = new_key
        mediafile["original_file_location"] = f"/download/{new_key}"
        mediafile[
            "thumbnail_file_location"
        ] = f"/iiif/3/{new_key}/full/,150/0/default.jpg"
        mediafile["mimetype"] = mimetype
        requests.put(
            f"{self.collection_api_url}/mediafiles/{mediafile_id}",
            json=mediafile,
            headers=self.headers,
        )

    def _get_mediafile(self, mediafile_id):
        req = requests.get(
            f"{self.collection_api_url}/mediafiles/{mediafile_id}", headers=self.headers
        )
        if req.status_code == 404:
            raise MediafileNotFoundException("Could not get mediafile with provided id")
        elif req.status_code != 200:
            raise Exception("Something went wrong while getting mediafile")
        return req.json()

    def is_metadata_updated(self, old_metadata, new_metadata):
        if len(old_metadata) != len(new_metadata):
            return True
        unmatched = list(old_metadata)
        for item in new_metadata:
            try:
                unmatched.remove(item)
            except ValueError:
                return True
        return len(unmatched) > 0

    def _signal_file_uploaded(self, mediafile, mimetype, url):
        attributes = {"type": "dams.file_uploaded", "source": "dams"}
        data = {"mediafile": mediafile, "mimetype": mimetype, "url": url}
        event = to_dict(CloudEvent(attributes, data))
        app.rabbit.send(event, routing_key="dams.file_uploaded")

    def __get_mimetype_from_filename(self, filename):
        mime = mimetypes.guess_type(filename, False)[0]
        return mime if mime else "application/octet-stream"

    def __get_file_mimetype(self, file):
        file.seek(0, 0)
        mime = magic.Magic(mime=True).from_buffer(file.read(parse_size("8 KiB")))
        file.seek(0, 0)
        if mime == "application/octet-stream":
            mime = self.__get_mimetype_from_filename(file.filename)
        return mime

    def __handle_duplicate_file(
        self, mediafile_id, mediafile, mimetype, md5sum, filename, message
    ):
        try:
            found_mediafile = self._get_mediafile(md5sum)
        except MediafileNotFoundException:
            self._update_mediafile_information(
                mediafile, md5sum, filename, mediafile_id, mimetype
            )
            message = (
                f"{message} No existing mediafile for file found, not deleting new one."
            )
            raise DuplicateFileException(message)
        requests.delete(
            f"{self.collection_api_url}/mediafiles/{mediafile_id}",
            headers=self.headers,
        )
        message = f"{message} Existing mediafile for file found, deleting new one."
        if self.is_metadata_updated(found_mediafile["metadata"], mediafile["metadata"]):
            message = f"{message} Metadata not up-to-date, updating."
            payload = {"metadata": mediafile["metadata"]}
            requests.patch(
                f"{self.collection_api_url}/mediafiles/{md5sum}",
                headers=self.headers,
                json=payload,
            )
        raise DuplicateFileException(message)

    def upload_file(self, file, mediafile_id, key=None):
        mediafile = self._get_mediafile(mediafile_id)
        if key is None:
            key = file.filename
        md5sum = self.__calculate_md5(file)
        mimetype = self.__get_file_mimetype(file)
        try:
            self.check_file_exists(file.filename, md5sum)
        except DuplicateFileException as ex:
            self.__handle_duplicate_file(
                mediafile_id, mediafile, mimetype, ex.md5sum, ex.filename, ex.message
            )
        key = f"{md5sum}-{key}"
        self.bucket.upload_fileobj(Fileobj=file, Key=key)
        self._update_mediafile_information(
            mediafile, md5sum, key, mediafile_id, mimetype
        )
        self._signal_file_uploaded(
            mediafile,
            mimetype,
            f'{self.storage_api_url}{mediafile["original_file_location"]}',
        )

    def upload_transcode(self, file, mediafile_id):
        mediafile = self._get_mediafile(mediafile_id)
        md5sum = self.__calculate_md5(file)
        key = f"{md5sum}-transcode-{file.filename}"
        self.check_file_exists(key, md5sum)
        self.bucket.upload_fileobj(Fileobj=file, Key=key)
        mediafile["identifiers"].append(md5sum)
        data = {
            "identifiers": mediafile["identifiers"],
            "transcode_filename": key,
            "transcode_file_location": f"/download/{key}",
            "thumbnail_file_location": f"/iiif/3/{key}/full/,150/0/default.jpg",
        }
        requests.patch(
            f"{self.collection_api_url}/mediafiles/{mediafile_id}",
            headers=self.headers,
            json=data,
        )

    def download_file(self, file_name):
        try:
            file_obj = io.BytesIO()
            self.bucket.download_fileobj(Key=file_name, Fileobj=file_obj)
        except ClientError:
            app.logger.error(f"File {file_name} not found")
            return None
        return file_obj

    def __get_item_metadata_value(self, item, key):
        for entry in item["metadata"]:
            if entry["key"] == key:
                return entry["value"]
        return False

    def __get_exif_for_mediafile(self, mediafile):
        artist = f'source: {self.__get_item_metadata_value(mediafile, "source")}'
        if photographer := self.__get_item_metadata_value(mediafile, "photographer"):
            artist = f"photographer: {photographer}, {artist}"
        rights = f'license: {self.__get_item_metadata_value(mediafile, "rights")}'
        if copyrights := self.__get_item_metadata_value(mediafile, "copyright"):
            rights = f"rightsholder: {copyrights}, {rights}"
        return artist, rights

    def add_exif_data(self, mediafile):
        if "image" not in mediafile["mimetype"]:
            return
        image = self.download_file(mediafile["filename"])
        img = Image.open(image)
        exif = img.getexif()
        exif[0x013B], exif[0x8298] = self.__get_exif_for_mediafile(mediafile)
        buf = io.BytesIO()
        img.save(buf, img.format, exif=exif)
        buf.seek(0)
        self.bucket.upload_fileobj(Fileobj=buf, Key=mediafile["filename"])

    def delete_files(self, files):
        payload = {"Objects": [{"Key": file} for file in files], "Quiet": True}
        self.bucket.delete_objects(Delete=payload)
