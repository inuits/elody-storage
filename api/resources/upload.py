import app
import tempfile

from flask import request
from flask_restful import abort
from inuits_jwt_auth.authorization import current_token
from resources.base_resource import BaseResource
from util import DuplicateFileException, MediafileNotFoundException
from werkzeug.datastructures import FileStorage


class Upload(BaseResource):
    def __get_file_object(self, key):
        if request.files:
            file = request.files["file"]
        else:
            file = tempfile.NamedTemporaryFile(mode="ab+")
            while chunk := request.stream.read(1024):
                file.write(chunk)
            file = FileStorage(stream=file, filename=key)
            if not file.filename:
                file.close()
                abort(400, message="Could not get filename for streamed object")
            file.seek(0)
        return file

    def __get_mediafile_id(self, req):
        if mediafile_id := req.args.get("id"):
            return mediafile_id
        raise MediafileNotFoundException("No mediafile id provided")

    @app.require_oauth("upload-file")
    def post(self, key=None, transcode=False):
        job = app.jobs_extension.create_new_job(
            f'Starting {"transcode" if transcode else "file"} upload',
            f'dams.upload_{"transcode" if transcode else "file"}',
            user=dict(current_token).get("email", "default_uploader"),
        )
        app.jobs_extension.progress_job(job, amount_of_jobs=1)
        try:
            file = self.__get_file_object(key)
            mediafile_id = self.__get_mediafile_id(request)
            app.jobs_extension.progress_job(job, mediafile_id=mediafile_id)
            if transcode:
                self.storage.upload_transcode(file, mediafile_id)
            else:
                self.storage.upload_file(file, mediafile_id, key)
        except DuplicateFileException as ex:
            app.jobs_extension.fail_job(job, message=str(ex))
            return str(ex), 409
        except Exception as ex:
            app.jobs_extension.fail_job(job, message=str(ex))
            return str(ex), 400
        app.jobs_extension.finish_job(
            job, message=f"Successfully uploaded {file.filename}"
        )
        file.close()
        return "", 201


class UploadKey(Upload):
    @app.require_oauth("upload-file-key")
    def post(self, key):
        return super().post(key)


class UploadTranscode(Upload):
    @app.require_oauth("upload-transcode")
    def post(self):
        return super().post(transcode=True)
