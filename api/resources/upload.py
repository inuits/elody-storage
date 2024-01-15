from resources.base_resource import BaseResource


class Upload(BaseResource):
    def post(self, ticket_id):
        try:
            ticket = self._get_ticket(ticket_id)
            transcode = ticket.get("transcode", False)
        except Exception as ex:
            return str(ex), 400
        return self._handle_file_upload(ticket=ticket, transcode=transcode)