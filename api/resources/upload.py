import app

from exceptions import DuplicateFileException
from flask import request
from resources.base_resource import BaseResource


class Upload(BaseResource):
    @app.require_oauth("upload-file")
    def post(self, key=None):
        job = app.jobs_extension.create_new_job(
            "Starting file upload", "dams.upload_file"
        )
        app.jobs_extension.progress_job(job, amount_of_jobs=1)
        try:
            file = request.files["file"]
            mediafile_id = self._get_mediafile_id(request)
            app.jobs_extension.progress_job(job, mediafile_id=mediafile_id)
            self.storage.upload_file(file, mediafile_id, key)
        except DuplicateFileException as ex:
            app.jobs_extension.fail_job(job, error_message=str(ex))
            return str(ex), 409
        except Exception as ex:
            app.jobs_extension.fail_job(job, error_message=str(ex))
            return str(ex), 400
        app.jobs_extension.finish_job(job)
        return "", 201


class UploadKey(Upload):
    @app.require_oauth("upload-file-key")
    def post(self, key):
        return super().post(key)


class UploadTranscode(BaseResource):
    @app.require_oauth("upload-transcode")
    def post(self):
        job = app.jobs_extension.create_new_job(
            "Starting transcode upload", "dams.upload_transcode"
        )
        app.jobs_extension.progress_job(job, amount_of_jobs=1)
        try:
            file = request.files["file"]
            mediafile_id = self._get_mediafile_id(request)
            app.jobs_extension.progress_job(job, mediafile_id=mediafile_id)
            self.storage.upload_transcode(file, mediafile_id)
        except Exception as ex:
            app.jobs_extension.fail_job(job, error_message=str(ex))
            return str(ex), 400
        app.jobs_extension.finish_job(job)
        return "", 201
