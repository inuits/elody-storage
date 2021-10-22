import os
from flask_restful import Resource, abort
from flask import send_file, after_this_request

from storage.storage import download_file

import app


class Download(Resource):
    token_required = os.getenv("REQUIRE_TOKEN", "True").lower() in ["true", "1"]

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
