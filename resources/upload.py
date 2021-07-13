import os
from flask_restful import Resource
from flask import request

from storage.storage import upload_file

import app

token_required = os.getenv("REQUIRE_TOKEN", "True").lower() in ["true", "1"]


class Upload(Resource):
    @app.oidc.accept_token(require_token=token_required, scopes_required=["openid"])
    def post(self):
        f = request.files["file"]
        upload_file(f)
        return "", 201


class UploadKey(Resource):
    @app.oidc.accept_token(require_token=token_required, scopes_required=["openid"])
    def post(self, key):
        f = request.files["file"]
        upload_file(f, key)
        return "", 201
