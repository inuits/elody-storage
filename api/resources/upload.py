import shutil
import tempfile

from app import jobs_extension, policy_factory
from elody.exceptions import DuplicateFileException, NotFoundException
from flask import request
from flask_restful import abort
from inuits_policy_based_auth.exceptions import NoUserContextException
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

    def _handle_file_upload(self, key=None, transcode=False):
        try:
            user = policy_factory.get_user_context().email or "default_uploader"
        except NoUserContextException:
            user = "default_uploader"
        job = jobs_extension.create_new_job(
            f'Starting {"transcode" if transcode else "file"} upload',
            f'dams.upload_{"transcode" if transcode else "file"}',
            user=user,
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

    @policy_factory.authenticate()
    def post(self, key=None, transcode=False):
        return self._handle_file_upload(key, transcode)


class UploadKey(Upload):
    @policy_factory.authenticate()
    def post(self, key):
        return super().post(key)


class UploadKeyWithTicket(Upload):
    def post(self, key):
        ticket_id = request.args.get("ticket_id")
        if not self.storage._is_valid_ticket(ticket_id):
            abort(403, message=f"Ticket with id {ticket_id} is not valid")
        return self._handle_file_upload(key)


class UploadTranscode(Upload):
    @policy_factory.authenticate()
    def post(self):
        return super().post(transcode=True)
