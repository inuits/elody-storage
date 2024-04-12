from app import logger, policy_factory
from flask import request
from inuits_policy_based_auth import RequestContext
from resources.base_resource import BaseResource
import time


class Download(BaseResource):
    @policy_factory.authenticate(RequestContext(request))
    def get(self, key):
        return self._handle_file_download(key)


class DownloadWithTicket(BaseResource):
    def head(self, key):
        return {}

    def get(self, key):
        try:
            start_time = time.time()
            ticket = self._get_ticket(
                request.args.get("ticket_id"), request.args.get("api_key_hash")
            )
        except Exception as ex:
            return str(ex), 400
        logger.info(f"Fetching ticket took {time.time() - start_time}s")
        return self._handle_file_download(key, ticket=ticket)
