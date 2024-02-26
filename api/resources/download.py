from app import policy_factory
from flask import request
from inuits_policy_based_auth import RequestContext
from resources.base_resource import BaseResource


class Download(BaseResource):
    @policy_factory.authenticate(RequestContext(request))
    def get(self, key):
        return self._handle_file_download(key)


class DownloadWithTicket(BaseResource):
    def get(self, key):
        try:
            ticket = self._get_ticket(
                request.args.get("ticket_id"), request.args.get("api_key_hash")
            )
        except Exception as ex:
            return str(ex), 400
        return self._handle_file_download(key, ticket=ticket)
