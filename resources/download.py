import os
from flask_restful import Resource, abort
from flask import send_file, after_this_request
from flask_restful_swagger import swagger

from storage.storage import download_file

import app


class Download(Resource):
    token_required = os.getenv("REQUIRE_TOKEN", "True").lower() in ["true", "1"]

    @swagger.operation(notes="Download a mediafile")
    @app.oidc.accept_token(require_token=token_required, scopes_required=["openid"])
    def get(self, filename):
        output = download_file(filename)
        if output is None:
            abort(
                404,
                message="File {} doesn't exist".format(filename),
            )

        @after_this_request
        def add_header(response):
            response.headers["Access-Control-Allow-Origin"] = "*"
            return response

        return send_file(output)
