import app
import magic

from flask import after_this_request, Response
from flask_restful import Resource, abort
from storage.storage import download_file


class Download(Resource):
    @app.require_oauth()
    def get(self, key):
        output = download_file(key)
        if output is None:
            abort(
                404,
                message="File {} doesn't exist".format(key),
            )

        @after_this_request
        def add_header(response):
            response.headers["Access-Control-Allow-Origin"] = "*"
            return response

        def read_file():
            output.seek(0, 0)
            data = output.read(1024)
            while data:
                yield data
                data = output.read(1024)

        mime = magic.Magic(mime=True).from_buffer(output.read(2048))
        return Response(read_file(), mimetype=mime)
