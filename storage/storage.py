import boto3
import os

s3 = boto3.resource(
    "s3",
    endpoint_url=os.getenv("MINIO_ENDPOINT"),
    aws_access_key_id=os.getenv("MINIO_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("MINIO_SECRET_KEY"),
)

bucket = os.getenv("MINIO_BUCKET")


def upload_file(file):
    """
    Function to upload a file to an S3 bucket
    """
    s3.Bucket(bucket).put_object(Key=file.filename, Body=file)

    return True


def download_file(file_name):
    """
    Function to download a given file from an S3 bucket
    """
    output = f"downloads/{file_name}"
    s3.Bucket(bucket).download_file(file_name, output)

    return output
