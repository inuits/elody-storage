import app

from flask import request
from flask_restful import Resource
from storage.storage import upload_file, upload_transcode


def _get_mediafile_id(req):
    if mediafile_id := req.args.get("id"):
        return mediafile_id
    raise Exception("No mediafile id provided")


class Upload(Resource):
    @app.require_oauth("upload-file")
    def post(self, key=None):
        try:
            file = request.files["file"]
            mediafile_id = _get_mediafile_id(request)
            upload_file(file, mediafile_id, key)
        except Exception as ex:
            return str(ex), 400
        return "", 201


class UploadKey(Upload):
    @app.require_oauth("upload-file-key")
    def post(self, key):
        return super().post(key)


class UploadTranscode(Resource):
    @app.require_oauth("upload-transcode")
    def post(self):
        try:
            file = request.files["file"]
            mediafile_id = _get_mediafile_id(request)
            upload_transcode(file, mediafile_id)
        except Exception as ex:
            return str(ex), 400
        return "", 201
