import uuid

from tests.base_case import BaseCase
from unittest.mock import patch


@patch("resources.upload.job_helper")
@patch("storage.storage._update_mediafile_information")
@patch("storage.storage._get_mediafile")
@patch("storage.storage._signal_file_uploaded")
class UploadFileTest(BaseCase):
    def test_upload_invalid_file(
        self,
        fake_job_helper,
        fake_update,
        fake_get_mediafile,
        fake_signal_file_uploaded,
    ):
        data = dict()
        data["file"] = "test.png"

        response = self.app.post(
            f"/upload?id={uuid.uuid4()}",
            headers={"content-type": "multipart/form-data"},
            data=data,
        )

        self.assertEqual(93, len(response.json))
        self.assertEqual(400, response.status_code)

    def test_upload_no_callback_url(
        self,
        fake_job_helper,
        fake_update,
        fake_get_mediafile,
        fake_signal_file_uploaded,
    ):
        data = dict()
        data["file"] = self.create_test_image()

        response = self.app.post(
            "/upload", headers={"content-type": "multipart/form-data"}, data=data
        )

        self.assertEqual("No mediafile id provided", response.json)
        self.assertEqual(400, response.status_code)

    def test_upload_with_callback_url(
        self,
        fake_job_helper,
        fake_update,
        fake_get_mediafile,
        fake_signal_file_uploaded,
    ):
        data = dict()
        data["file"] = self.create_test_image()

        response = self.app.post(
            f"/upload?id={uuid.uuid4()}",
            headers={"content-type": "multipart/form-data"},
            data=data,
        )

        self.assertEqual("", response.json)
        self.assertEqual(201, response.status_code)
