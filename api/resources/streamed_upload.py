from app import policy_factory
from elody.exceptions import DuplicateFileException, EmptyFileException
from flask import request
from inuits_policy_based_auth import RequestContext
from resources.base_resource import BaseResource
from werkzeug.exceptions import BadRequest


class InitStream(BaseResource):
    @policy_factory.authenticate(RequestContext(request))
    def post(self):
        try:
            if not (mediafile_id := request.args.get("mediafile_id")):
                raise BadRequest("Missing required query parameter 'mediafile_id'")
            stream_id = self.store.init_stream(key=mediafile_id)
            return {"stream_id": stream_id, "mediafile_id": mediafile_id}, 200
        except BadRequest as ex:
            return str(ex), 400
        except Exception as ex:
            return str(ex), 500


class SignChunk(BaseResource):
    @policy_factory.authenticate(RequestContext(request))
    def post(self):
        try:
            request_body = request.get_json()
            upload_url = self.store.sign_chunk(
                stream_id=request_body["stream_id"],
                key=request_body["mediafile_id"],
                chunk_sequence=int(request_body["chunk_sequence"]),
            )
            return {"upload_url": upload_url}, 200
        except BadRequest as ex:
            return str(ex), 400
        except Exception as ex:
            return str(ex), 500


class CompleteStream(BaseResource):
    @policy_factory.authenticate(RequestContext(request))
    def post(self):
        try:
            request_body = request.get_json()
            self.store.complete_stream(
                stream_id=request_body["stream_id"],
                key=request_body["mediafile_id"],
                chunks_info=request_body["chunks_info"],
                file_info=request_body["file_info"],
                legacy_store=self.storage,
            )
        except EmptyFileException as ex:
            return ex.message, 422
        except DuplicateFileException as ex:
            return str(ex), 409 if isinstance(ex, DuplicateFileException) else 400
        except BadRequest as ex:
            return str(ex), 400
        except Exception as ex:
            return str(ex), 500


class AbortStream(BaseResource):
    @policy_factory.authenticate(RequestContext(request))
    def post(self):
        try:
            request_body = request.get_json()
            self.store.abort_stream(
                stream_id=request_body["stream_id"], key=request_body["mediafile_id"]
            )
            return {}, 204
        except BadRequest as ex:
            return str(ex), 400
        except Exception as ex:
            return str(ex), 500
