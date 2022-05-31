import app
import boto3
import hashlib
import io
import json
import magic
import mimetypes
import os
import requests

from botocore.exceptions import ClientError
from cloudevents.http import CloudEvent, to_json
from humanfriendly import parse_size
from PIL import Image

s3 = boto3.resource(
    "s3",
    endpoint_url=os.getenv("MINIO_ENDPOINT"),
    aws_access_key_id=os.getenv("MINIO_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("MINIO_SECRET_KEY"),
)
bucket = os.getenv("MINIO_BUCKET")
headers = {"Authorization": "Bearer {}".format(os.getenv("STATIC_JWT", "None"))}
collection_api_url = os.getenv("COLLECTION_API_URL")
storage_api_url = os.getenv("STORAGE_API_URL")


class DuplicateFileException(Exception):
    def __init__(self, error_message, existing_file=None, md5sum=None):
        super().__init__(error_message)
        self.error_message = error_message
        self.existing_file = existing_file
        self.md5sum = md5sum


def check_file_exists(filename, md5sum):
    objects = s3.Bucket(bucket).meta.client.list_objects_v2(
        Bucket=bucket, Prefix=md5sum
    )
    if len(objects.get("Contents", [])):
        existing_file = objects.get("Contents", [])[0]["Key"]
        error_message = (
            f"Duplicate file {filename} matches existing file {existing_file}."
        )
        raise DuplicateFileException(error_message, existing_file, md5sum)


def calculate_md5(file):
    hash_obj = hashlib.md5()
    while chunk := file.read(parse_size("8 KiB")):
        hash_obj.update(chunk)
    file.seek(0, 0)
    return hash_obj.hexdigest()


def _update_mediafile_information(mediafile, md5sum, new_key, mediafile_id, mimetype):
    mediafile["identifiers"].append(md5sum)
    mediafile["original_filename"] = mediafile["filename"]
    mediafile["filename"] = new_key
    mediafile["original_file_location"] = f"/download/{new_key}"
    mediafile["thumbnail_file_location"] = f"/iiif/3/{new_key}/full/,150/0/default.jpg"
    mediafile["mimetype"] = mimetype
    requests.put(
        f"{collection_api_url}/mediafiles/{mediafile_id}",
        json=mediafile,
        headers=headers,
    )


def _get_mediafile(mediafile_id):
    req = requests.get(
        f"{collection_api_url}/mediafiles/{mediafile_id}", headers=headers
    )
    if req.status_code != 200:
        raise Exception("Could not get mediafile with provided id")
    return req.json()


def is_metadata_updated(old_metadata, new_metadata):
    if len(old_metadata) != len(new_metadata):
        return True
    unmatched = list(old_metadata)
    for item in new_metadata:
        try:
            unmatched.remove(item)
        except ValueError:
            return True
    return len(unmatched) > 0


def _signal_file_uploaded(mediafile, mimetype, url):
    attributes = {"type": "dams.file_uploaded", "source": "dams"}
    data = {"mediafile": mediafile, "mimetype": mimetype, "url": url}
    event = CloudEvent(attributes, data)
    message = json.loads(to_json(event))
    app.rabbit.send(message, routing_key="dams.file_uploaded")


def __get_mimetype_from_filename(filename):
    mime = mimetypes.guess_type(filename, False)[0]
    return mime if mime else "application/octet-stream"


def _get_file_mimetype(file):
    file.seek(0, 0)
    mime = magic.Magic(mime=True).from_buffer(file.read(parse_size("8 KiB")))
    file.seek(0, 0)
    if mime == "application/octet-stream":
        mime = __get_mimetype_from_filename(file.filename)
    return mime


def __upload_to_s3(file, key):
    mpu = s3.Bucket(bucket).meta.client.create_multipart_upload(Bucket=bucket, Key=key)
    part_num = 1
    parts = []
    while chunk := file.read(parse_size("50 MiB")):
        part = s3.Bucket(bucket).meta.client.upload_part(
            Body=chunk,
            Bucket=bucket,
            Key=key,
            PartNumber=part_num,
            UploadId=mpu["UploadId"],
        )
        parts.append({"PartNumber": part_num, "ETag": part["ETag"]})
        part_num = part_num + 1
    s3.Bucket(bucket).meta.client.complete_multipart_upload(
        Bucket=bucket,
        Key=key,
        MultipartUpload={"Parts": parts},
        UploadId=mpu["UploadId"],
    )


def upload_file(file, mediafile_id, key=None):
    mediafile = _get_mediafile(mediafile_id)
    if key is None:
        key = file.filename
    md5sum = calculate_md5(file)
    mimetype = _get_file_mimetype(file)
    try:
        check_file_exists(file.filename, md5sum)
    except DuplicateFileException as ex:
        try:
            found_mediafile = _get_mediafile(ex.md5sum)
        except Exception:
            _update_mediafile_information(
                mediafile, ex.md5sum, ex.existing_file, mediafile_id, mimetype
            )
            error_message = f"{ex.error_message} No existing mediafile for file found, not deleting new one."
            raise DuplicateFileException(error_message)
        requests.delete(
            f"{collection_api_url}/mediafiles/{mediafile_id}", headers=headers
        )
        error_message = (
            f"{ex.error_message} Existing mediafile for file found, deleting new one."
        )
        if is_metadata_updated(found_mediafile["metadata"], mediafile["metadata"]):
            error_message = f"{error_message} Metadata not up-to-date, updating."
            payload = {"metadata": mediafile["metadata"]}
            requests.patch(
                f"{collection_api_url}/mediafiles/{ex.md5sum}",
                headers=headers,
                json=payload,
            )
        raise DuplicateFileException(error_message)
    key = f"{md5sum}-{key}"
    __upload_to_s3(file, key)
    _update_mediafile_information(mediafile, md5sum, key, mediafile_id, mimetype)
    _signal_file_uploaded(
        mediafile, mimetype, f'{storage_api_url}{mediafile["original_file_location"]}'
    )


def upload_transcode(file, mediafile_id):
    mediafile = _get_mediafile(mediafile_id)
    md5sum = calculate_md5(file)
    new_filename = f'{os.path.splitext(mediafile["original_filename"])[0]}.jpg'
    key = f"{md5sum}-transcode-{new_filename}"
    check_file_exists(key, md5sum)
    __upload_to_s3(file, key)
    mediafile["identifiers"].append(md5sum)
    data = {
        "identifiers": mediafile["identifiers"],
        "transcode_filename": key,
        "transcode_file_location": f"/download/{key}",
        "thumbnail_file_location": f"/iiif/3/{key}/full/,150/0/default.jpg",
    }
    requests.patch(
        f"{collection_api_url}/mediafiles/{mediafile_id}",
        headers=headers,
        json=data,
    )


def download_file(file_name):
    try:
        file_obj = s3.Bucket(bucket).meta.client.get_object(
            Bucket=bucket, Key=file_name
        )
    except ClientError:
        app.logger.error(f"File {file_name} not found")
        return None
    return file_obj["Body"]


def _get_exif_strings(metadata):
    merged_metadata = {
        "copyright": "",
        "photographer": "",
        "rights": "",
        "source": "",
        "publication_status": "",
    }
    for item in metadata:
        merged_metadata[item["key"]] = item["value"]
    artist = merged_metadata.get("source")
    if photographer := merged_metadata.get("photographer"):
        artist = f"{artist} - {photographer}"
    rights = merged_metadata.get("rights")
    if copyrights := merged_metadata.get("copyright"):
        rights = f"{rights} - {copyrights}"
    return {"artist": artist, "copyright": rights}


def add_exif_data(mediafile):
    if "image" not in mediafile["mimetype"]:
        return
    image = download_file(mediafile["filename"])
    exif_strings = _get_exif_strings(mediafile["metadata"])
    img = Image.open(image)
    exif = img.getexif()
    img.load()
    exif[0x013B] = exif_strings["artist"]
    exif[0x8298] = exif_strings["copyright"]
    buf = io.BytesIO()
    img.save(buf, img.format, exif=exif)
    buf.seek(0)
    __upload_to_s3(buf, mediafile["filename"])


def delete_file(mediafile):
    try:
        s3.Bucket(bucket).meta.client.delete_object(
            Bucket=bucket, Key=mediafile["filename"]
        )
        if "transcode_filename" in mediafile:
            s3.Bucket(bucket).meta.client.delete_object(
                Bucket=bucket, Key=mediafile["transcode_filename"]
            )
    except ClientError as ce:
        app.logger.error(f"Failed to delete file(s) {ce}")
