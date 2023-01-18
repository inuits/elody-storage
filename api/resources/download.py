import app
import magic

from exceptions import FileNotFoundException
from flask import after_this_request, Response
from flask_restful import abort
from humanfriendly import parse_size
from resources.base_resource import BaseResource


class Download(BaseResource):
    @app.require_oauth("download-file")
    def get(self, key):
        try:
            output = self.storage.download_file(key)
        except FileNotFoundException as ex:
            abort(404, message=str(ex))

        @after_this_request
        def add_header(response):
            response.headers["Access-Control-Allow-Origin"] = "*"
            return response

        def read_file():
            while data := output.read(parse_size("1 MiB")):
                yield data

        mime = magic.Magic(mime=True).from_buffer(output.read(parse_size("8 KiB")))
        output.seek(0)
        return Response(read_file(), mimetype=mime)
