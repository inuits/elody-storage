import os
from flask_restful import Resource
from flask import request
from flask_restful_swagger import swagger

from storage.storage import upload_file

import app

token_required = os.getenv("REQUIRE_TOKEN", "True").lower() in ["true", "1"]


class Upload(Resource):
    @swagger.operation(notes="Upload a mediafile")
    @app.oidc.accept_token(require_token=token_required, scopes_required=["openid"])
    def post(self):
        f = request.files["file"]
        upload_file(f)
        return "", 201


class UploadKey(Resource):
    @swagger.operation(notes="Upload a mediafile using a key")
    @app.oidc.accept_token(require_token=token_required, scopes_required=["openid"])
    def post(self, key):
        f = request.files["file"]
        upload_file(f, key)
        return "", 201
