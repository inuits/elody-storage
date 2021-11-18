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


def _update_mediafile_file_location(mediafile, part_to_add, url, duplicate=False):
    if duplicate:
        mediafile["original_file_location"] = "/download/{}".format(part_to_add)
        mediafile[
            "thumbnail_file_location"
        ] = "/iiif/3/{}/full/,150/0/default.jpg".format(part_to_add)
    else:
        original_file = mediafile["original_file_location"][10:]
        mediafile["original_file_location"] = "/download/{}-{}".format(
            part_to_add, original_file
        )
        mediafile[
            "thumbnail_file_location"
        ] = "/iiif/3/{}-{}/full/,150/0/default.jpg".format(part_to_add, original_file)
    requests.put(
        url,
        json=mediafile,
        headers={"Authorization": "Bearer {}".format(os.getenv("STATIC_JWT", "None"))},
    )


def _get_mediafile(url):
    req = requests.get(
        url,
        headers={"Authorization": "Bearer {}".format(os.getenv("STATIC_JWT", "None"))},
    )
    if req.status_code != 200:
        raise Exception("Callback url did not lead to existing mediafile")
    return req.json()


def upload_file(file, url, key=None):
    raw_url = url + "?raw=1"
    mediafile = _get_mediafile(raw_url)
    if key is None:
        key = file.filename
    md5sum = calculate_md5(file)
    try:
        check_file_exists(file.filename, md5sum)
    except DuplicateFileException as ex:
        _update_mediafile_file_location(mediafile, ex.existing_file, url, True)
        error_message = (
            ex.error_message
            + " Mediafile & entity file locations were relinked to existing file."
        )
        raise DuplicateFileException(error_message)
    key = "{}-{}".format(md5sum, key)
    _update_mediafile_file_location(mediafile, md5sum, url)
    s3.Bucket(bucket).put_object(Key=key, Body=file)


def download_file(file_name):
    output = f"downloads/{file_name}"
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    try:
        s3.Bucket(bucket).download_file(file_name, output)
    except botocore.exceptions.ClientError as e:
        return None
    return Path(output).absolute()
