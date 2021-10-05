from tests.base_case import BaseCase
from unittest.mock import patch


class DownloadFileTest(BaseCase):
    @patch("resources.upload.job_helper")
    def test_download(self, fake_job_helper):
        data = dict()
        data["file"] = self.create_test_image()
        md5 = self.calculate_md5(data["file"])

        self.app.post(
            "/upload", headers={"content-type": "multipart/form-data"}, data=data
        )

        response = self.app.get("/download/{}-test.png".format(md5))

        self.assertEqual(200, response.status_code)

    def test_non_existent_image_download(self):
        response = self.app.get("/download/test.png")

        self.assertEqual(1, len(response.json))
        self.assertEqual(str, type(response.json["message"]))
        self.assertEqual("File test.png doesn't exist", response.json["message"])
        self.assertEqual(404, response.status_code)
