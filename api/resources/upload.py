import shutil
import tempfile

from app import jobs_extension, policy_factory
from elody.exceptions import DuplicateFileException, NotFoundException
from flask import request
from resources.base_resource import BaseResource


class Upload(BaseResource):
    def __get_file_object(self):
        if request.files:
            file = request.files["file"]
        else:
            file = tempfile.NamedTemporaryFile(mode="ab+")
            shutil.copyfileobj(request.stream, file)
            file.seek(0)
        return file

    def __get_key_for_file(self, key, file):
        if key:
            return key
        if getattr(file, "filename", None):
            return file.filename
        if getattr(file, "name", None):
            return file.name
        raise Exception("Could not determine filename for upload")

    def __get_mediafile_id(self, req):
        if mediafile_id := req.args.get("id"):
            return mediafile_id
        raise NotFoundException("No mediafile id provided")

    @policy_factory.authenticate()
    def post(self, key=None, transcode=False):
        job = jobs_extension.create_new_job(
            f'Starting {"transcode" if transcode else "file"} upload',
            f'dams.upload_{"transcode" if transcode else "file"}',
            user=policy_factory.get_user_context().email or "default_uploader",
        )
        jobs_extension.progress_job(job, amount_of_jobs=1)
        file = None
        try:
            file = self.__get_file_object()
            key = self.__get_key_for_file(key, file)
            mediafile_id = self.__get_mediafile_id(request)
            jobs_extension.progress_job(job, mediafile_id=mediafile_id)
            if transcode:
                self.storage.upload_transcode(file, mediafile_id, key)
            else:
                self.storage.upload_file(file, mediafile_id, key)
        except (DuplicateFileException, Exception) as ex:
            if file:
                file.close()
            jobs_extension.fail_job(job, message=str(ex))
            return str(ex), 409 if isinstance(ex, DuplicateFileException) else 400
        jobs_extension.finish_job(job, message=f"Successfully uploaded {key}")
        file.close()
        return "", 201


class UploadKey(Upload):
    @policy_factory.authenticate()
    def post(self, key):
        return super().post(key)


class UploadTranscode(Upload):
    @policy_factory.authenticate()
    def post(self):
        return super().post(transcode=True)
