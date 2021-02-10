import os
from flask_restful import Resource
from flask import request
from flask_restful_swagger import swagger

from storage.storage import upload_file

import app

class Upload(Resource):
    @swagger.operation(notes="Upload a mediafile")
    @app.oidc.accept_token(require_token=True, scopes_required=['openid'])
    def post(self):
        f = request.files['file']
        upload_file(f)
        return 201 
