from app import policy_factory
from flask import request
from inuits_policy_based_auth import RequestContext
from resources.base_resource import BaseResource
from storage.storagemanager import StorageManager


class Upload(BaseResource):
    @policy_factory.authenticate(RequestContext(request))
    def post(self):
        parent_job_id = request.args.get("parent_job_id")
        user = (
            request.args.get("user_email")
            or request.headers.get("X-User-Email")
            or (ticket.get("user") if isinstance(ticket, dict) else getattr(ticket, "user", None))
            or None
        )
        if user:
            self.auth_headers["X-User-Email"] = user
        return self._handle_file_upload(parent_job_id=parent_job_id, user=user)


class UploadWithTicket(BaseResource):
    def post(self):
        try:
            ticket = self._get_ticket(request.args.get("ticket_id"))
            parent_job_id = request.args.get("parent_job_id")
            user = (
                request.args.get("user_email")
                or request.headers.get("X-User-Email")
                or (ticket.get("user") if isinstance(ticket, dict) else getattr(ticket, "user", None))
                or None
            )
        except Exception as ex:
            return str(ex), 400
        
        if user:
            self.auth_headers["X-User-Email"] = user
        return self._handle_file_upload(
            ticket=ticket, parent_job_id=parent_job_id, user=user
        )


class UploadKey(BaseResource):
    @policy_factory.authenticate(RequestContext(request))
    def post(self, key):
        parent_job_id = request.args.get("parent_job_id")
        user = (
            request.args.get("user_email")
            or request.headers.get("X-User-Email")
            or (ticket.get("user") if isinstance(ticket, dict) else getattr(ticket, "user", None))
            or None
        )
        if user:
            self.auth_headers["X-User-Email"] = user
        return self._handle_file_upload(key=key, parent_job_id=parent_job_id, user=user)


class UploadKeyWithTicket(BaseResource):
    def post(self, key):
        try:
            ticket = self._get_ticket(request.args.get("ticket_id"))
            parent_job_id = request.args.get("parent_job_id")
            user = (
                request.args.get("user_email")
                or request.headers.get("X-User-Email")
                or (ticket.get("user") if isinstance(ticket, dict) else getattr(ticket, "user", None))
                or None
            )
        except Exception as ex:
            return str(ex), 400
        if user:
            self.auth_headers["X-User-Email"] = user
        return self._handle_file_upload(
            key=key, ticket=ticket, parent_job_id=parent_job_id, user=user
        )


class UploadTranscode(BaseResource):
    @policy_factory.authenticate(RequestContext(request))
    def post(self):
        try:
            ticket_id = request.args.get("ticket_id")
            parent_job_id = request.args.get("parent_job_id")
            user = (
                request.args.get("user_email")
                or request.headers.get("X-User-Email")
                or (ticket.get("user") if isinstance(ticket, dict) else getattr(ticket, "user", None))
                or None
            )
            if ticket_id:
                ticket = self._get_ticket(ticket_id)
                return self._handle_file_upload(
                    transcode=True,
                    ticket=ticket,
                    parent_job_id=parent_job_id,
                    user=user,
                )
            else:
                return self._handle_file_upload(
                    transcode=True, parent_job_id=parent_job_id, user=user
                )
        except Exception as ex:
            return str(ex), 400
