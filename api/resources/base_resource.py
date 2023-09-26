import re
import shutil
import tempfile

from app import jobs_extension, policy_factory
from elody.exceptions import (
    DuplicateFileException,
    NotFoundException,
    FileNotFoundException,
)
from elody.util import get_mimetype_from_filename
from flask import request, Response, stream_with_context
from flask_restful import Resource, abort
from inuits_policy_based_auth.exceptions import NoUserContextException
from storage.storagemanager import StorageManager
from werkzeug.datastructures import Headers


class BaseResource(Resource):
    def __init__(self):
        self.storage = StorageManager().get_storage_engine()

    def __get_byte_range(self, range_header):
        g = re.search("(\d+)-(\d*)", range_header).groups()
        byte1, byte2, length = 0, None, None
        if g[0]:
            byte1 = int(g[0])
        if g[1]:
            byte2 = int(g[1])
            length = byte2 + 1 - byte1
        return byte1, byte2, length

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

    def _handle_file_download(self, key, ticket=None):
        chunk = False
        try:
            file_object = self.storage.download_file(key, ticket=ticket)
        except FileNotFoundException as ex:
            abort(404, message=str(ex))
        content_type = get_mimetype_from_filename(key)
        full_length = file_object["content_length"]
        headers = Headers()
        headers["Accept-Ranges"] = "bytes"
        headers["Content-Type"] = content_type
        headers["Content-Length"] = full_length
        if range_header := request.headers.get("Range"):
            byte_start, byte_end, length = self.__get_byte_range(range_header)
            if byte_end:
                chunk = True
                file_object = self.storage.download_file(
                    key, f"bytes={byte_start}-{byte_end}", ticket
                )
                end = byte_start + length - 1
                headers["Content-Range"] = f"bytes {byte_start}-{end}/{full_length}"
                headers["Content-Transfer-Encoding"] = "binary"
                headers["Connection"] = "Keep-Alive"
                headers["Content-Type"] = content_type
                headers["Content-Length"] = file_object["content_length"]
                if byte_end == 1:
                    headers["Content-Length"] = "1"
        response = Response(
            stream_with_context(
                self.storage.get_stream_generator(file_object["stream"])
            ),
            mimetype=content_type,
            content_type=content_type,
            headers=headers,
            status=206 if chunk else 200,
            direct_passthrough=chunk,
        )
        return response

    def _handle_file_upload(self, key=None, transcode=False, ticket=None):
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
            if not (mediafile_id := request.args.get("id")) and not ticket:
                raise NotFoundException("Provide either a mediafile ID or a ticket ID")
            jobs_extension.progress_job(job, mediafile_id=mediafile_id)
            if transcode:
                self.storage.upload_transcode(file, mediafile_id, key)
            else:
                self.storage.upload_file(file, mediafile_id, key, ticket)
        except (DuplicateFileException, Exception) as ex:
            if file:
                file.close()
            jobs_extension.fail_job(job, message=str(ex))
            return str(ex), 409 if isinstance(ex, DuplicateFileException) else 400
        jobs_extension.finish_job(job, message=f"Successfully uploaded {key}")
        file.close()
        return "", 201
