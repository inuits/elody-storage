import unittest
import json

from tests.base_case import BaseCase


class DownloadFileTest(BaseCase):
    def test_download(self):
        data = dict()
        data["file"] = self.create_test_image()

        self.app.post(
            "/upload", headers={"content-type": "multipart/form-data"}, data=data
        )

        response = self.app.get("/download/test.png")

        self.assertEqual(200, response.status_code)

    def test_non_existent_image_download(self):
        response = self.app.get("/download/test.png")

        self.assertEqual(1, len(response.json))
        self.assertEqual(str, type(response.json["message"]))
        self.assertEqual("File test.png doesn't exist", response.json["message"])
        self.assertEqual(404, response.status_code)
