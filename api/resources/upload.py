import app

from flask import request
from resources.base_resource import BaseResource


class Upload(BaseResource):
    @app.require_oauth("upload-file")
    def post(self, key=None):
        try:
            file = request.files["file"]
            mediafile_id = self.__get_mediafile_id(request)
            self.storage.upload_file(file, mediafile_id, key)
        except Exception as ex:
            return str(ex), 400
        return "", 201


class UploadKey(Upload):
    @app.require_oauth("upload-file-key")
    def post(self, key):
        return super().post(key)


class UploadTranscode(BaseResource):
    @app.require_oauth("upload-transcode")
    def post(self):
        try:
            file = request.files["file"]
            mediafile_id = self.__get_mediafile_id(request)
            self.storage.upload_transcode(file, mediafile_id)
        except Exception as ex:
            return str(ex), 400
        return "", 201
