import os
from flask_restful import Resource
from flask import send_file

from storage.storage import download_file

import app

class Download(Resource):
    @app.oidc.accept_token(require_token=True, scopes_required=['openid'])
    def get(self, filename):
        output = download_file(filename)
        return send_file(output, as_attachment=True)
