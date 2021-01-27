import os
from flask_restful import Resource
from flask import send_file

from storage.storage import download_file

class Download(Resource):
    def get(self, filename):
        output = download_file(filename)
        return send_file(output, as_attachment=True)
