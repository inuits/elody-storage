import app

from exceptions import DuplicateFileException, MediafileNotFoundException
from flask import request
from resources.base_resource import BaseResource


class Upload(BaseResource):
    def __get_mediafile_id(self, req):
        if mediafile_id := req.args.get("id"):
            return mediafile_id
        raise MediafileNotFoundException("No mediafile id provided")

    @app.require_oauth("upload-file")
    def post(self, key=None, transcode=False):
        job = app.jobs_extension.create_new_job(
            f'Starting {"transcode" if transcode else "file"} upload',
            f'dams.upload_{"transcode" if transcode else "file"}',
        )
        app.jobs_extension.progress_job(job, amount_of_jobs=1)
        try:
            file = request.files["file"]
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
        app.jobs_extension.finish_job(job)
        return "", 201


class UploadKey(Upload):
    @app.require_oauth("upload-file-key")
    def post(self, key):
        return super().post(key)


class UploadTranscode(Upload):
    @app.require_oauth("upload-transcode")
    def post(self):
        return super().post(transcode=True)
