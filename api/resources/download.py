import app

from flask import after_this_request, send_file
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

        return send_file(output)
