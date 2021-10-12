from tests.base_case import BaseCase
from unittest.mock import patch


@patch("resources.upload.job_helper")
class UploadFileTest(BaseCase):
    def test_upload(self, fake_job_helper):
        data = dict()
        data["file"] = self.create_test_image()

        response = self.app.post(
            "/upload", headers={"content-type": "multipart/form-data"}, data=data
        )

        self.assertFalse(response.json)
        self.assertEqual(201, response.status_code)

    def test_invalid_file_upload(self, fake_job_helper):
        data = dict()
        data["file"] = "test.png"

        response = self.app.post(
            "/upload", headers={"content-type": "multipart/form-data"}, data=data
        )

        self.assertEqual(400, response.status_code)
