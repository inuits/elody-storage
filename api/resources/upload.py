from app import policy_factory
from flask import request
from flask_restful import abort
from inuits_policy_based_auth import RequestContext
from resources.base_resource import BaseResource


class Upload(BaseResource):
    @policy_factory.authenticate(RequestContext(request))
    def post(self):
        return self._handle_file_upload()


class UploadWithTicket(BaseResource):
    def post(self):
        ticket_id = request.args.get("ticket_id")
        if not self.storage.is_valid_ticket(ticket_id):
            abort(403, message=f"Ticket with id {ticket_id} is not valid")
        # FIXME: pass ticket to use as source of info
        return self._handle_file_upload()


class UploadKey(BaseResource):
    @policy_factory.authenticate(RequestContext(request))
    def post(self, key):
        return self._handle_file_upload(key=key)


class UploadKeyWithTicket(BaseResource):
    def post(self, key):
        ticket_id = request.args.get("ticket_id")
        if not self.storage.is_valid_ticket(ticket_id):
            abort(403, message=f"Ticket with id {ticket_id} is not valid")
        # FIXME: pass ticket to use as source of info (except for key)
        return self._handle_file_upload(key=key)


class UploadTranscode(BaseResource):
    @policy_factory.authenticate(RequestContext(request))
    def post(self):
        return self._handle_file_upload(transcode=True)
