import boto3
import botocore
import os

s3 = boto3.resource(
    "s3",
    endpoint_url=os.getenv("MINIO_ENDPOINT"),
    aws_access_key_id=os.getenv("MINIO_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("MINIO_SECRET_KEY"),
)

bucket = os.getenv("MINIO_BUCKET")


def upload_file(file, key=None):
    """
    Function to upload a file to an S3 bucket
    """
    if key is None:
        key = file.filename
    s3.Bucket(bucket).put_object(Key=key, Body=file)

    return True


def download_file(file_name):
    """
    Function to download a given file from an S3 bucket
    """
    output = f"downloads/{file_name}"
    try:
        s3.Bucket(bucket).download_file(file_name, output)
    except botocore.exceptions.ClientError as e:
        return None
    return output
