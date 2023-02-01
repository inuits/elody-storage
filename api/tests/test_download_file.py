import uuid

from tests.base_case import BaseCase
from unittest.mock import patch, MagicMock


@patch("app.jobs_extension", new=MagicMock())
@patch("app.rabbit", new=MagicMock())
@patch("requests.put", new=MagicMock())
@patch("storage.s3store.S3StorageManager._get_mediafile", new=MagicMock())
class DownloadFileTest(BaseCase):
    def test_download(self):
        data = dict()
        data["file"] = self.create_test_image()
        md5 = self.calculate_md5(data["file"])

        self.app.post(
            f"/upload?id={uuid.uuid4()}",
            headers={"content-type": "multipart/form-data"},
            data=data,
        )

        response = self.app.get("/download/{}-test.png".format(md5))

        self.assertEqual(200, response.status_code)

    def test_download_non_existent_image(self):
        response = self.app.get("/download/test.png")

        self.assertEqual(1, len(response.json))
        self.assertEqual(str, type(response.json["message"]))
        self.assertEqual("File test.png not found", response.json["message"])
        self.assertEqual(404, response.status_code)
