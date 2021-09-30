import boto3
import botocore
import hashlib
import os

from pathlib import Path

s3 = boto3.resource(
    "s3",
    endpoint_url=os.getenv("MINIO_ENDPOINT"),
    aws_access_key_id=os.getenv("MINIO_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("MINIO_SECRET_KEY"),
)
bucket = os.getenv("MINIO_BUCKET")


def check_file_exists(file, md5sum):
    objects = s3.Bucket(bucket).meta.client.list_objects_v2(Bucket=bucket)
    for obj in objects.get("Contents", []):
        metadata = s3.Bucket(bucket).meta.client.head_object(
            Bucket=bucket, Key=obj["Key"]
        )
        if md5sum == metadata["Metadata"]["md5sum"]:
            raise Exception(
                "Duplicate file detected. {} matches existing file {}".format(
                    file, obj["Key"]
                )
            )


def calculate_md5(file):
    hash_obj = hashlib.md5()
    while chunk := file.read(8192):
        hash_obj.update(chunk)
    file.seek(0, 0)
    return hash_obj.hexdigest()


def upload_file(file, key=None):
    if key is None:
        key = file.filename
    md5sum = calculate_md5(file)
    check_file_exists(file.filename, md5sum)
    s3.Bucket(bucket).put_object(Key=key, Body=file, Metadata={"md5sum": md5sum})


def download_file(file_name):
    output = f"downloads/{file_name}"
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    try:
        s3.Bucket(bucket).download_file(file_name, output)
    except botocore.exceptions.ClientError as e:
        return None
    return output
