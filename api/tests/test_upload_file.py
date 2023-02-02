import uuid

from tests.base_case import BaseCase
from unittest.mock import patch, MagicMock


@patch("app.jobs_extension", new=MagicMock())
@patch("app.rabbit", new=MagicMock())
@patch("requests.put", new=MagicMock())
@patch("storage.s3store.S3StorageManager._get_mediafile", new=MagicMock())
class UploadFileTest(BaseCase):
    def test_upload_no_callback_url(self):
        response = self.app.post(
            "/upload",
            headers={"content-type": "multipart/form-data"},
            data={"file": self.create_test_image()},
        )

        self.assertEqual("No mediafile id provided", response.json)
        self.assertEqual(400, response.status_code)

    def test_upload_with_callback_url(self):
        response = self.app.post(
            f"/upload?id={uuid.uuid4()}",
            headers={"content-type": "multipart/form-data"},
            data={"file": self.create_test_image()},
        )

        self.assertEqual("", response.json)
        self.assertEqual(201, response.status_code)

    def test_upload_duplicate_file(self):
        image1 = self.create_test_image()
        image2 = self.create_test_image()

        self.assertEqual(image1.read(), image2.read())

        image1.seek(0)

        response = self.app.post(
            f"/upload?id={uuid.uuid4()}",
            headers={"content-type": "multipart/form-data"},
            data={"file": image1},
        )

        self.assertEqual("", response.json)
        self.assertEqual(201, response.status_code)

        image2.seek(0)

        response = self.app.post(
            f"/upload?id={uuid.uuid4()}",
            headers={"content-type": "multipart/form-data"},
            data={"file": image2},
        )

        self.assertEqual(
            "Duplicate file test.png matches existing file 6daf79d9e12c350f105e099915ce7b02-test.png.",
            response.json,
        )
        self.assertEqual(409, response.status_code)
