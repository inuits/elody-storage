import os
from flask_restful import Resource
from flask import send_file, after_this_request
from flask_restful_swagger import swagger

from storage.storage import download_file

import app


class Download(Resource):
    @swagger.operation(notes="Download a mediafile")
    @app.oidc.accept_token(require_token=True, scopes_required=["openid"])
    def get(self, filename):
        output = download_file(filename)

        @after_this_request
        def add_header(response):
            response.headers["Access-Control-Allow-Origin"] = "*"
            return response

        return send_file(output)
