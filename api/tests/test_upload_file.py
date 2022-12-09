import uuid

from tests.base_case import BaseCase
from unittest.mock import patch, MagicMock


@patch("app.jobs_extension", new=MagicMock())
@patch("app.rabbit", new=MagicMock())
@patch("storage.s3store.S3StorageManager._get_mediafile", new=MagicMock())
@patch("storage.s3store.S3StorageManager._signal_file_uploaded", new=MagicMock())
@patch(
    "storage.s3store.S3StorageManager._update_mediafile_information", new=MagicMock()
)
class UploadFileTest(BaseCase):
    def test_upload_invalid_file(self):
        data = dict()
        data["file"] = "test.png"

        response = self.app.post(
            f"/upload?id={uuid.uuid4()}",
            headers={"content-type": "multipart/form-data"},
            data=data,
        )

        self.assertEqual(93, len(response.json))
        self.assertEqual(400, response.status_code)

    def test_upload_no_callback_url(self):
        data = dict()
        data["file"] = self.create_test_image()

        response = self.app.post(
            "/upload", headers={"content-type": "multipart/form-data"}, data=data
        )

        self.assertEqual("No mediafile id provided", response.json)
        self.assertEqual(400, response.status_code)

    def test_upload_with_callback_url(self):
        data = dict()
        data["file"] = self.create_test_image()

        response = self.app.post(
            f"/upload?id={uuid.uuid4()}",
            headers={"content-type": "multipart/form-data"},
            data=data,
        )

        self.assertEqual("", response.json)
        self.assertEqual(201, response.status_code)
