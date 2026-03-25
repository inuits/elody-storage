import app
import boto3
import hashlib
import io
import magic
import os
import re
import requests
from rabbit import get_rabbit

from botocore.exceptions import ClientError
from cloudevents.conversion import to_dict
from cloudevents.http import CloudEvent
from dateutil import parser
from elody.error_codes import ErrorCode, get_error_code, get_write
from elody.exceptions import (
    DuplicateFileException,
    FileNotFoundException,
    NotFoundException,
    EmptyFileException,
)
from elody.util import get_mimetype_from_filename
from humanfriendly import parse_size
from PIL import Image, ExifTags, TiffImagePlugin
from urllib.parse import urlparse

NEW_STORAGE_ENABLED = os.getenv("NEW_STORAGE_ENABLED", "False") in [
    "true",
    "True",
    True,
]


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
        self.duplicate_file_check = os.getenv("DUPLICATE_FILE_CHECK", True)
        self.access_control_list = (
            (os.getenv("ACCESS_CONTROL_LIST") or "").lower().strip().split(",")
        )
        self.access_control_type = os.getenv("ACCESS_CONTROL_TYPE", "deny").lower()
        Image.MAX_IMAGE_PIXELS = 300000000

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

    def __convert_filesize(self, filesize_bytes):
        # NOTE: This function currently divides by 1024 for each step in the
        # conversion. According to the internet that's how windows calculates
        # it, but that does seem to be a mismatch on linux. For example, a file
        # that shows as 2.0 mb on linux is calculated as being 1.99 MB
        si_sufffixes = {
            0: "B",
            1: "KB",
            2: "MB",
            3: "GB",
            4: "TB",
            5: "PB",
        }
        counter = 0

        while 1 << 10 < filesize_bytes and counter < 5:
            filesize_bytes = filesize_bytes / (1 << 10)
            counter += 1
        return f"{round(filesize_bytes, 2)} {si_sufffixes[counter]}"

    def __get_filesize(self, file):
        original_file_position = file.tell()
        try:
            file.seek(0, os.SEEK_END)
            filesize_bytes = file.tell()
            return self.__convert_filesize(filesize_bytes)

        except (io.UnsupportedOperation, AttributeError):
            return None
        finally:
            file.seek(original_file_position)

    def __get_filesize_s3(self, key, bucket):
        try:
            file_headers = self.s3.Bucket(bucket).meta.client.head_object(
                Bucket=bucket, Key=key
            )
            if filesize_bytes := file_headers.get("ContentLength"):
                return self.__convert_filesize(filesize_bytes)
            return None
        except:
            return None

    def __get_exif_for_mediafile(self, mediafile):
        artist = f"source: {self.__get_item_metadata_value(mediafile, 'source')}"
        if photographer := self.__get_item_metadata_value(mediafile, "photographer"):
            artist = f"photographer: {photographer}, {artist}"
        rights = f"license: {self.__get_item_metadata_value(mediafile, 'rights')}"
        if copyrights := self.__get_item_metadata_value(mediafile, "copyright"):
            rights = f"rightsholder: {copyrights}, {rights}"
        return artist, rights

    def __get_file_content(self, file, mimetype):
        file_content = None
        if mimetype == "text/plain":
            file.seek(0)
            raw_data = file.read()
            file.seek(0)
            file_content = (
                raw_data.decode("utf-8") if isinstance(raw_data, bytes) else raw_data
            )
        return file_content

    def __get_file_mimetype(self, file, key):
        file.seek(0)
        mime = magic.Magic(mime=True).from_buffer(file.read(parse_size("8 KiB")))
        file.seek(0)
        if mime == "application/octet-stream":
            mime = get_mimetype_from_filename(key)
        self.__valiate_mimetype_access_control(mime)
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
            raise DuplicateFileException(
                f"{get_error_code(ErrorCode.DUPLICATE_FILE, get_write())} {message}"
            )
        mediafile_id = self.__get_raw_id(mediafile)
        if self.__get_raw_id(found_mediafile) != mediafile_id:
            self.session.delete(f"{self.collection_api_url}/mediafiles/{mediafile_id}")
            message = f"{message} Existing mediafile for file found, deleting new one."
        if self.is_metadata_updated(found_mediafile, mediafile):
            # NOTE: So this currently means the last seen filename is used.
            message = f"{message} Metadata not up-to-date, updating."
            payload = {
                "metadata": mediafile.get("metadata", []),
                "schema": {"type": "elody"},
                "type": "mediafile",
            }
            self.session.patch(
                f"{self.collection_api_url}/mediafiles/{md5sum}", json=payload
            )
        if (
            self.are_relations_updated(found_mediafile, mediafile)
            and NEW_STORAGE_ENABLED
        ):
            message = f"{message} Relations not up-to-date, updating."
            relations_payload = self.get_relations_payload(found_mediafile, mediafile)
            self.session.put(
                f"{self.collection_api_url}/mediafiles/{md5sum}/relations",
                json=relations_payload,
            )
        raise DuplicateFileException(
            f"{get_error_code(ErrorCode.DUPLICATE_FILE, get_write())} {message}"
        )

    def __valiate_mimetype_access_control(self, mimetype):
        has_access_control = False
        if self.access_control_type == "allow":
            has_access_control = mimetype in self.access_control_list
        elif self.access_control_type == "deny":
            has_access_control = mimetype not in self.access_control_list
        if not has_access_control:
            raise Exception(f"File mimetype {mimetype} is not allowed.")

    def __signal_file_uploaded(
        self, mediafile, mimetype, url, headers, ticket=None, parent_job_id=None
    ):
        attributes = {"type": "dams.file_uploaded", "source": "dams"}
        data = {
            "mediafile": mediafile,
            "mimetype": mimetype,
            "url": url,
            "headers": headers,
            "ticket": ticket,
            "parent_job_id": parent_job_id,
        }
        event = to_dict(CloudEvent(attributes, data))
        get_rabbit().send(event, routing_key="dams.file_uploaded")

    def __update_mediafile_information(
        self,
        mediafile,
        md5sum,
        new_key,
        mimetype,
        exif_data=None,
        *,
        file_content=None,
    ):
        new_key = new_key.split("/")[-1]
        mediafile["identifiers"].append(md5sum)
        mediafile["md5sum"] = md5sum
        mediafile["original_filename"] = mediafile["filename"]
        if not mediafile.get(
            "technical_origin"
        ):  # It will otherwise overwrite the original if already present
            mediafile["technical_origin"] = "original"
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
        if (
            file_content
            and mimetype == "text/plain"
            and (
                parent_mediafile_ids := [
                    relation["key"]
                    for relation in mediafile.get("relations", [])
                    if relation["type"] == "isOcrFor"
                ]
            )
        ):
            self.session.patch(
                f"{self.collection_api_url}/mediafiles/{parent_mediafile_ids[0]}",
                json={
                    "metadata": [{"key": "text_from_ocr", "value": file_content}],
                    "schema": {"type": "elody"},
                    "type": "mediafile",
                },
            )

    def _get_mediafile(self, mediafile_id, fatal=True):
        req = self.session.get(f"{self.collection_api_url}/mediafiles/{mediafile_id}")
        if req.status_code == 200:
            return req.json()
        elif not fatal:
            return None
        elif req.status_code == 404:
            raise NotFoundException(
                f"{get_error_code(ErrorCode.MEDIAFILE_NOT_FOUND, get_write())} Could not get mediafile with provided id '{mediafile_id}'"
            )
        else:
            app.logger.error(
                f"Received weird response from collection-api:\nstatus_code: {req.status_code}\nresponse content: {req.json()}"
            )
            raise Exception(
                f"{get_error_code(ErrorCode.MEDIAFILE_NOT_FOUND, get_write())} Something went wrong while getting mediafile "
            )

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
            f"{self.collection_api_url}/mediafiles/{mediafile['identifiers'][0]}",
            json={"exif": str(exif), "schema": {"type": "elody"}, "type": "mediafile"},
        )

    def check_file_exists(self, filename, md5sum, ticket=None):
        if self.duplicate_file_check in ["True", True, "true"]:
            bucket_name = self.__get_bucket_name(ticket)
            client = self.s3.Bucket(bucket_name).meta.client
            objects = client.list_objects_v2(Bucket=bucket_name, Prefix=md5sum)
            if len(objects.get("Contents", [])):
                existing_file = objects.get("Contents", [])[0]["Key"]
                error_message = f" | existing_file:{existing_file} - Duplicate file {filename} matches existing file {existing_file}."
                raise DuplicateFileException(
                    f"{get_error_code(ErrorCode.DUPLICATE_FILE, get_write())} {error_message}",
                    existing_file,
                    md5sum,
                )

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
            raise FileNotFoundException(
                f"{get_error_code(ErrorCode.FILE_NOT_FOUND, get_write())} {message}"
            )
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
        old_metadata = [
            f"{metadata['key']}:{metadata['value']}"
            for metadata in old_mediafile.get("metadata", [])
        ]
        new_metadata = [
            f"{metadata['key']}:{metadata['value']}"
            for metadata in new_mediafile.get("metadata", [])
        ]
        return bool(set(new_metadata) - set(old_metadata))

    def are_relations_updated(self, old_mediafile, new_mediafile):
        old_relations = [
            f"{relation['key']}:{relation['type']}"
            for relation in old_mediafile.get("relations", [])
        ]
        new_relations = [
            f"{relation['key']}:{relation['type']}"
            for relation in new_mediafile.get("relations", [])
        ]
        return bool(set(new_relations) - set(old_relations))

    def get_relations_payload(self, old_mediafile, new_mediafile):
        old_relations = old_mediafile.get("relations", [])
        new_relations = new_mediafile.get("relations", [])
        for item in old_relations:
            new_relations = [
                relation
                for relation in new_relations
                if relation["key"] != item["key"] or relation["type"] != item["type"]
            ]

        return new_relations + old_relations

    def __get_bucket_name(self, ticket=None):
        if ticket:
            return ticket["bucket"]
        if bucket := os.getenv("MINIO_BUCKET"):
            return bucket
        raise Exception(
            f"{get_error_code(ErrorCode.NO_BUCKET_SPECIFIED, get_write())} No bucket for upload was specified"
        )

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
            return "(Binary data suppressed)"
        elif isinstance(value, (tuple, list)):
            return [self._handle_value_to_be_serializable(v) for v in value]
        elif isinstance(value, dict):
            return {
                k: self._handle_value_to_be_serializable(v) for k, v in value.items()
            }
        else:
            return value

    def _check_keys_and_extract_creation_dates(self, exif_data):
        keys_to_check = [
            "exif_datetime",
            "Xmp.xmp.CreateDate",
            "Xmp.xmp.MetadataDate",
            "Xmp.dc.date",
            "DateTimeDigitized",
            "DateTimeOriginal",
        ]
        for item in exif_data:
            if item["key"] in keys_to_check:
                date_str = item["value"]
                try:
                    date_obj = parser.parse(date_str)
                    iso_date_str = date_obj.isoformat()
                    return iso_date_str
                except ValueError:
                    return date_str
        return None

    def upload_file(self, file, mediafile_id, key, ticket, parent_job_id=None):
        mediafile = self._get_mediafile(mediafile_id)

        md5sum = self.__calculate_md5(file)
        mimetype = self.__get_file_mimetype(file, key)
        if md5sum == "d41d8cd98f00b204e9800998ecf8427e":
            if (
                key.split(".")[-1] == "txt"
            ):  # cannot detect based on mimetype, since mimetype of all emtpy files is "aplication/x-empty"
                message = f"File {key} is empty."
                raise EmptyFileException(
                    f"{get_error_code(ErrorCode.EMPTY_FILE, get_write())} {message}",
                    key,
                )
            raise Exception("Empty file, upload aborted")
        file_content = self.__get_file_content(file, mimetype)
        exif_data = (
            self._get_exif_data(file) if mimetype.startswith("image") else list()
        )
        mediafile["file_creation_date"] = self._check_keys_and_extract_creation_dates(
            exif_data
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
            bucket = ticket.get("bucket")
            mediafile["filesize"] = self.__get_filesize_s3(
                key, bucket
            ) or self.__get_filesize(file)
            self.__update_mediafile_information(
                mediafile,
                md5sum,
                key,
                mimetype,
                exif_data,
                file_content=file_content,
            )
            mediafile = self._get_mediafile(mediafile_id)
            download_url = urlparse(mediafile["original_file_location"])
            self.__signal_file_uploaded(
                mediafile,
                mimetype,
                f"{re.sub(r'/storage/v1/?$', '', self.storage_api_url)}{download_url.path}?{download_url.query}",
                self.headers,
                ticket,
                parent_job_id,
            )

    def upload_transcode(
        self,
        file,
        mediafile_id,
        key,
        ticket,
        ignore_duplicate_check: bool = False,
    ):
        md5sum = self.__calculate_md5(file)
        if md5sum == "d41d8cd98f00b204e9800998ecf8427e":
            raise Exception("Empty file, upload aborted")
        key = self.__get_key(key, md5sum=md5sum, transcode=True, ticket=ticket)
        mimetype = self.__get_file_mimetype(file, key)
        try:
            self.check_file_exists(key, md5sum)
            self.s3.Bucket(self.__get_bucket_name(ticket)).upload_fileobj(
                Fileobj=file, Key=key
            )
        except DuplicateFileException as ex:
            if not ignore_duplicate_check or not NEW_STORAGE_ENABLED:
                raise ex

        new_key = key.split("/")[-1]
        original_filename = self.__get_filename_from_key(key)

        data = {
            "filename": key,
            "md5sum": md5sum,
            "transcode_file_location": f"/download/{new_key}",
            "thumbnail_file_location": f"/iiif/3/{new_key}/full/,150/0/default.jpg",
            "original_filename": original_filename,
            "technical_origin": "transcode",
            "mimetype": mimetype,
        }
        bucket = self.__get_bucket_name(ticket)
        data["filesize"] = self.__get_filesize_s3(key, bucket) or self.__get_filesize(
            file
        )
        try:
            self.session.post(
                f"{self.collection_api_url}/mediafiles/{mediafile_id}/derivatives",
                json=data,
            )
            self.session.patch(
                f"{self.collection_api_url}/mediafiles/{mediafile_id}",
                json={
                    "display_filename": key,
                    "schema": {"type": "elody"},
                    "type": "mediafile",
                },
            )
        except Exception as ex:
            raise Exception(str(ex))

    def __get_filename_from_key(self, key):
        uuid_pattern = re.compile(r"[0-9a-fA-F]{32}-")
        original_filename = uuid_pattern.sub("", key)
        return original_filename
