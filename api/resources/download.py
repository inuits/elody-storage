from app import policy_factory
from flask import request, Response
from inuits_policy_based_auth import RequestContext
from resources.base_resource import BaseResource


class Download(BaseResource):
    def get(self, ticket_id):
        try:
            ticket = self._get_ticket(ticket_id)
        except Exception as ex:
            return str(ex), 400
        return self._handle_file_download(ticket)
