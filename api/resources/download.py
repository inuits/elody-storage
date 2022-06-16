import app
import magic

from flask import after_this_request, Response
from flask_restful import Resource, abort
from humanfriendly import parse_size
from storage.storage import download_file


class Download(Resource):
    @app.require_oauth("download-file")
    def get(self, key):
        output = download_file(key)
        if not output:
            abort(404, message=f"File {key} doesn't exist")

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
