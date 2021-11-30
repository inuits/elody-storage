from tests.base_case import BaseCase
from unittest.mock import patch


@patch("resources.upload.job_helper")
@patch("storage.storage._update_mediafile_information")
@patch("storage.storage._get_mediafile")
class DownloadFileTest(BaseCase):
    def test_download(self, fake_job_helper, fake_update, fake_get_mediafile):
        data = dict()
        data["file"] = self.create_test_image()
        md5 = self.calculate_md5(data["file"])

        self.app.post(
            "/upload?url=http://test.com",
            headers={"content-type": "multipart/form-data"},
            data=data,
        )

        response = self.app.get("/download/{}-test.png".format(md5))

        self.assertEqual(200, response.status_code)

    def test_download_non_existent_image(
        self, fake_job_helper, fake_update, fake_get_mediafile
    ):
        response = self.app.get("/download/test.png")

        self.assertEqual(1, len(response.json))
        self.assertEqual(str, type(response.json["message"]))
        self.assertEqual("File test.png doesn't exist", response.json["message"])
        self.assertEqual(404, response.status_code)
