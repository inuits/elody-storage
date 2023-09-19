from app import policy_factory
from flask import request
from flask_restful import abort
from inuits_policy_based_auth import RequestContext
from resources.base_resource import BaseResource


class Download(BaseResource):
    @policy_factory.authenticate(RequestContext(request))
    def get(self, key):
        return self._handle_file_download(key)


class DownloadWithTicket(BaseResource):
    def get(self, key):
        ticket_id = request.args.get("ticket_id")
        if not self.storage.is_valid_ticket(ticket_id):
            abort(403, message=f"Ticket with id {ticket_id} is not valid")
        return self._handle_file_download(key)
