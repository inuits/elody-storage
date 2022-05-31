import boto3
import hashlib
import os
import unittest

from app import app
from humanfriendly import parse_size
from io import BytesIO
from PIL import Image

s3 = boto3.resource(
    "s3",
    endpoint_url=os.getenv("MINIO_ENDPOINT"),
    aws_access_key_id=os.getenv("MINIO_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("MINIO_SECRET_KEY"),
)

bucket = os.getenv("MINIO_BUCKET")


class BaseCase(unittest.TestCase):
    def setUp(self):
        app.testing = True

        self.app = app.test_client()
        s3.create_bucket(Bucket=bucket)

    def tearDown(self):
        s3.Bucket(bucket).objects.all().delete()
        s3.Bucket(bucket).delete()

    def create_test_image(self):
        file = BytesIO()
        image = Image.new("RGBA", size=(50, 50), color=(155, 0, 0))
        image.save(file, "png")
        file.name = "test.png"
        file.seek(0)
        return file

    def calculate_md5(self, file):
        hash_obj = hashlib.md5()
        while chunk := file.read(parse_size("8 KiB")):
            hash_obj.update(chunk)
        file.seek(0, 0)
        return hash_obj.hexdigest()
