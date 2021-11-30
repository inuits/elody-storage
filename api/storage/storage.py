import boto3
import botocore
import hashlib
import os
import requests

from pathlib import Path

s3 = boto3.resource(
    "s3",
    endpoint_url=os.getenv("MINIO_ENDPOINT"),
    aws_access_key_id=os.getenv("MINIO_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("MINIO_SECRET_KEY"),
)
bucket = os.getenv("MINIO_BUCKET")
headers = {"Authorization": "Bearer {}".format(os.getenv("STATIC_JWT", "None"))}


class DuplicateFileException(Exception):
    def __init__(self, error_message, existing_file=None):
        super().__init__(error_message)
        self.existing_file = existing_file
        self.error_message = error_message


def check_file_exists(filename, md5sum):
    objects = s3.Bucket(bucket).meta.client.list_objects_v2(
        Bucket=bucket, Prefix=md5sum
    )
    if len(objects.get("Contents", [])):
        error_message = "Duplicate file {} matches existing file {}".format(
            filename, objects.get("Contents", [])[0]["Key"]
        )
        raise DuplicateFileException(
            error_message, objects.get("Contents", [])[0]["Key"]
        )


def calculate_md5(file):
    hash_obj = hashlib.md5()
    while chunk := file.read(8192):
        hash_obj.update(chunk)
    file.seek(0, 0)
    return hash_obj.hexdigest()


def _update_mediafile_information(mediafile, new_key, url):
    mediafile["original_filename"] = mediafile["filename"]
    mediafile["filename"] = new_key
    mediafile["original_file_location"] = f"/download/{new_key}"
    mediafile["thumbnail_file_location"] = f"/iiif/3/{new_key}/full/,150/0/default.jpg"
    requests.put(url, json=mediafile, headers=headers)


def _get_mediafile(url):
    req = requests.get(url, headers=headers)
    if req.status_code != 200:
        raise Exception("Callback url did not lead to existing mediafile")
    return req.json()


def upload_file(file, url, key=None):
    mediafile = _get_mediafile(f"{url}?raw=1")
    if key is None:
        key = file.filename
    md5sum = calculate_md5(file)
    try:
        check_file_exists(file.filename, md5sum)
    except DuplicateFileException as ex:
        _update_mediafile_information(mediafile, ex.existing_file, url)
        error_message = f"{ex.error_message} Mediafile & entity file locations were relinked to existing file."
        raise DuplicateFileException(error_message)
    key = f"{md5sum}-{key}"
    _update_mediafile_information(mediafile, key, url)
    s3.Bucket(bucket).put_object(Key=key, Body=file)


def download_file(file_name):
    output = f"downloads/{file_name}"
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    try:
        s3.Bucket(bucket).download_file(file_name, output)
    except botocore.exceptions.ClientError as e:
        return None
    return Path(output).absolute()
