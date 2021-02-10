import os
from flask_restful import Resource
from flask import request

from storage.storage import upload_file

import app

class Upload(Resource):
    @app.oidc.accept_token(require_token=True, scopes_required=['openid'])
    def post(self):
        f = request.files['file']
        upload_file(f)
        return 201 
