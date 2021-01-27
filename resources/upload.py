import os
from flask_restful import Resource
from flask import request

from storage.storage import upload_file

class Upload(Resource):
    def post(self):
        f = request.files['file']
        upload_file(f)
        return 201 
