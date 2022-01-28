import app
import boto3
import hashlib
import io
import os
import piexif
import requests

from botocore.exceptions import ClientError

s3 = boto3.resource(
    "s3",
    endpoint_url=os.getenv("MINIO_ENDPOINT"),
    aws_access_key_id=os.getenv("MINIO_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("MINIO_SECRET_KEY"),
)
bucket = os.getenv("MINIO_BUCKET")
headers = {"Authorization": "Bearer {}".format(os.getenv("STATIC_JWT", "None"))}
collection_api_url = os.getenv("COLLECTION_API_URL", "http://localhost:8000")


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
            f"Duplicate file {filename} matches existing file {existing_file}"
        )
        raise DuplicateFileException(error_message, existing_file, md5sum)


def calculate_md5(file):
    hash_obj = hashlib.md5()
    while chunk := file.read(8192):
        hash_obj.update(chunk)
    file.seek(0, 0)
    return hash_obj.hexdigest()


def _update_mediafile_information(mediafile, md5sum, new_key, mediafile_id):
    mediafile["identifiers"].append(md5sum)
    mediafile["original_filename"] = mediafile["filename"]
    mediafile["filename"] = new_key
    mediafile["original_file_location"] = f"/download/{new_key}"
    mediafile["thumbnail_file_location"] = f"/iiif/3/{new_key}/full/,150/0/default.jpg"
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


def add_exif_data(image, metadata):
    if not len(metadata):
        return
    merged_metadata = {
        "rights": "",
        "copyright": "",
        "photographer": "",
        "source": "",
    }
    image_bytes = image.read()
    image.seek(0)
    exif = piexif.load(image_bytes)
    for item in metadata:
        merged_metadata[item["key"]] = item["value"]
    artist = f'{merged_metadata.get("photographer")} - {merged_metadata.get("source")}'
    copyrights = f'{merged_metadata.get("rights")} - {merged_metadata.get("copyright")}'
    exif["0th"][piexif.ImageIFD.Artist] = artist.encode("UTF-8")
    exif["0th"][piexif.ImageIFD.Copyright] = copyrights.encode("UTF-8")
    exif_bytes = piexif.dump(exif)
    image_copy = io.BytesIO()
    piexif.insert(exif_bytes, image_bytes, image_copy)
    image.stream = image_copy


def upload_file(file, mediafile_id, key=None):
    mediafile = _get_mediafile(mediafile_id)
    if key is None:
        key = file.filename
    md5sum = calculate_md5(file)
    try:
        check_file_exists(file.filename, md5sum)
    except DuplicateFileException as ex:
        try:
            found_mediafile = _get_mediafile(ex.md5sum)
            requests.delete(
                f"{collection_api_url}/mediafiles/{mediafile_id}", headers=headers
            )
            if set(found_mediafile["metadata"]) != set(mediafile["metadata"]):
                found_mediafile["metadata"] = mediafile["metadata"]
                requests.put(
                    f"{collection_api_url}/mediafiles/{ex.md5sum}",
                    headers=headers,
                    json=found_mediafile,
                )
                # add_exif_data(file, mediafile["metadata"])
                s3.Bucket(bucket).put_object(Key=ex.existing_file, Body=file)
            error_message = f"{ex.error_message} Existing mediafile for file found, deleting new one."
        except Exception:
            _update_mediafile_information(
                mediafile, ex.md5sum, ex.existing_file, mediafile_id
            )
            error_message = f"{ex.error_message} No existing mediafile for file found, not deleting new one."
        raise DuplicateFileException(error_message)
    key = f"{md5sum}-{key}"
    _update_mediafile_information(mediafile, md5sum, key, mediafile_id)
    if "metadata" not in mediafile:
        mediafile["metadata"] = []
    # add_exif_data(file, mediafile["metadata"])
    s3.Bucket(bucket).put_object(Key=key, Body=file)


def download_file(file_name):
    try:
        file_obj = s3.Bucket(bucket).meta.client.get_object(
            Bucket=bucket, Key=file_name
        )
    except ClientError:
        app.logger.error(f"File {file_name} not found")
        return None
    return io.BytesIO(file_obj["Body"].read())
