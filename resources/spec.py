from flask_restful import Resource
from flask import send_from_directory

import app


class OpenAPISpec(Resource):
    def get(self):
        return send_from_directory("docs", "dams-storage-api.json")
