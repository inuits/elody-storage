from app import policy_factory
from flask import request
from inuits_policy_based_auth import RequestContext
from resources.base_resource import BaseResource


class Upload(BaseResource):
    @policy_factory.authenticate(RequestContext(request))
    def post(self):
        return self._handle_file_upload()


class UploadWithTicket(BaseResource):
    def post(self):
        try:
            ticket = self.storage.get_ticket(request.args.get("ticket_id"))
        except Exception as ex:
            return str(ex), 400
        return self._handle_file_upload(ticket=ticket)


class UploadKey(BaseResource):
    @policy_factory.authenticate(RequestContext(request))
    def post(self, key):
        return self._handle_file_upload(key=key)


class UploadKeyWithTicket(BaseResource):
    def post(self, key):
        try:
            ticket = self.storage.get_ticket(request.args.get("ticket_id"))
        except Exception as ex:
            return str(ex), 400
        return self._handle_file_upload(key=key, ticket=ticket)


class UploadTranscode(BaseResource):
    @policy_factory.authenticate(RequestContext(request))
    def post(self):
        return self._handle_file_upload(transcode=True)
