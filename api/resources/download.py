from app import policy_factory
from flask import request, Response
from inuits_policy_based_auth import RequestContext
from resources.base_resource import BaseResource


class Download(BaseResource):
    @policy_factory.authenticate(RequestContext(request))
    def get(self, key):
        return self._handle_file_download(key)


class DownloadWithTicket(BaseResource):
    def head(self, key):
        headers = dict()
        file_info = self.storage.get_file_info(key)
        for s3_key, header_key in {
            "AcceptRanges": "Accept-Ranges",
            "ContentLength": "Content-Length",
            "ContentType": "Content-Type",
        }.items():
            if s3_key in file_info:
                headers[header_key] = file_info[s3_key]
        return Response(headers=headers)

    def get(self, key):
        try:
            ticket = self._get_ticket(
                request.args.get("ticket_id"), request.args.get("api_key_hash")
            )
        except Exception as ex:
            return str(ex), 400
        return self._handle_file_download(key, ticket=ticket)
