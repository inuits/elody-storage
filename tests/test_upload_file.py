from tests.base_case import BaseCase


class UploadFileTest(BaseCase):
    def test_upload(self):
        data = dict()
        data["file"] = self.create_test_image()

        response = self.app.post(
            "/upload", headers={"content-type": "multipart/form-data"}, data=data
        )

        self.assertFalse(response.json)
        self.assertEqual(201, response.status_code)

    def test_invalid_file_upload(self):
        data = dict()
        data["file"] = "test.png"

        response = self.app.post(
            "/upload", headers={"content-type": "multipart/form-data"}, data=data
        )

        self.assertEqual(400, response.status_code)
