import os
import re
import requests
import shutil
import tempfile

from app import get_user_context
from rabbit import get_rabbit
from elody.error_codes import ErrorCode, get_error_code, get_write
from elody.exceptions import (
    DuplicateFileException,
    NotFoundException,
    FileNotFoundException,
)
from elody.job import init_job, start_job, finish_job, fail_job
from elody.util import get_mimetype_from_filename
from flask import request, Response, stream_with_context
from flask_restful import Resource, abort
from inuits_policy_based_auth.exceptions import NoUserContextException
from storage.storagemanager import StorageManager
from werkzeug.datastructures import Headers


class BaseResource(Resource):
    def __init__(self):
        self.auth_headers = self.__get_auth_headers()
        user_header = request.headers.get('X-User-Email')
        if user_header:
            self.auth_headers["X-User-Email"] = user_header
        self.storage = StorageManager().get_storage_engine(self.auth_headers)
        self.collection_api_url = os.getenv("COLLECTION_API_URL")

    def __get_auth_headers(self):
        try:
            tenant = get_user_context().x_tenant.id
        except NoUserContextException:
            tenant = request.headers.get("apikey", os.getenv("STATIC_APIKEY"))
        if tenant:
            return {
                "Authorization": f'Bearer {os.getenv("STATIC_JWT")}',
                "apikey": tenant,
            }
        else:
            return {"Authorization": f'Bearer {os.getenv("STATIC_JWT")}'}

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
        raise Exception(
            f"{get_error_code(ErrorCode.NO_FILENAME_SPECIFIED, get_write())} Could not determine filename for upload"
        )

    def _get_ticket(self, ticket_id, api_key_hash=None):
        if not ticket_id:
            raise Exception(
                f"{get_error_code(ErrorCode.NO_TICKET_ID_SPECIFIED, get_write())} No ticket id given"
            )
        request_url = f"{self.collection_api_url}/tickets/{ticket_id}"
        if api_key_hash:
            request_url = f"{request_url}?api_key_hash={api_key_hash}"
        response = requests.get(request_url, headers=self.auth_headers)
        if response.status_code != 200:
            raise NotFoundException(
                f"{get_error_code(ErrorCode.TICKET_NOT_FOUND, get_write())} Ticket with id {ticket_id} not found"
            )
        ticket = response.json()
        if ticket.get("is_expired", True):
            raise Exception(
                f"{get_error_code(ErrorCode.TICKET_EXPIRED, get_write())} Ticket is expired"
            )
        return ticket

    def _handle_file_download(self, key, ticket=None):
        try:
            file_object = self.storage.download_file(key, ticket=ticket)
        except FileNotFoundException as ex:
            abort(404, message=str(ex))

        full_length = file_object["content_length"]
        content_type = get_mimetype_from_filename(key)
        headers = Headers()
        headers["Accept-Ranges"] = "bytes"
        headers["Content-Type"] = content_type

        range_header = request.headers.get("Range")
        if range_header:
            byte_start, byte_end, length = self.__get_byte_range(range_header)
            if byte_end is None:
                byte_end = full_length - 1
                length = byte_end + 1 - byte_start

            file_object = self.storage.download_file(
                key, f"bytes={byte_start}-{byte_end}", ticket
            )

            headers["Content-Range"] = f"bytes {byte_start}-{byte_end}/{full_length}"
            headers["Content-Length"] = file_object["content_length"]
            return Response(
                stream_with_context(
                    self.storage.get_stream_generator(file_object["stream"])
                ),
                mimetype=content_type,
                headers=headers,
                status=206,
                direct_passthrough=True,
            )

        headers["Content-Length"] = full_length
        return Response(
            stream_with_context(
                self.storage.get_stream_generator(file_object["stream"])
            ),
            mimetype=content_type,
            headers=headers,
            status=200,
            direct_passthrough=False,
        )

    def _handle_file_upload(
        self, key=None, transcode=False, ticket=None, parent_job_id=None, user=None
    ):
        if not user:
            user_header = request.headers.get('X-User-Email')
            if user_header:
                user = user_header
            else:
                try:
                    user = get_user_context().email or "default_uploader"
                except NoUserContextException:
                    user = "default_uploader"
        job_id = None
        file = None
        try:
            if not (mediafile_id := request.args.get("id")) and not ticket:
                raise NotFoundException(
                    f"{get_error_code(ErrorCode.PROVIDE_MEDIAFILE_ID_OR_TICKET_ID, get_write())} Provide either a mediafile ID or a ticket ID"
                )
            if not mediafile_id and "mediafile_id" in ticket:
                mediafile_id = ticket.get("mediafile_id")
            file = self.__get_file_object()
            key = self.__get_key_for_file(key, file)
            parent_job_id = request.view_args.get("parent_job_id") or parent_job_id
            job_id = init_job(
                f"Upload {key}{' transcode' if transcode else ''}",
                "File upload",
                get_rabbit=get_rabbit,
                user_email=user,
                parent_id=parent_job_id,
                id_of_document_job_was_initiated_for=mediafile_id,
            )
            start_job(job_id, get_rabbit=get_rabbit)
            if transcode:
                self.storage.upload_transcode(file, mediafile_id, key, ticket)
            else:
                self.storage.upload_file(
                    file, mediafile_id, key, ticket, parent_job_id=parent_job_id
                )
        except (DuplicateFileException, Exception) as ex:
            if file:
                file.close()
            if job_id:
                fail_job(job_id, str(ex), get_rabbit=get_rabbit)
            return str(ex), 409 if isinstance(ex, DuplicateFileException) else 400
        finally:
            if file:
                file.close()
        finish_job(job_id, get_rabbit=get_rabbit)
        return "", 201

    def get_user_from_request_and_ticket(self, request, ticket=None):
        user = (
                request.args.get("user_email")
                or request.headers.get("X-User-Email")
                or (
                    (ticket.get("user") if isinstance(ticket, dict) else getattr(ticket, "user", None))
                    if ticket is not None else None
                )
                or None
        )
        if user:
            self.auth_headers["X-User-Email"] = user
        return user
