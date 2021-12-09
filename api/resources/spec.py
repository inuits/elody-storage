from flask import send_from_directory
from flask_restful import Resource


class OpenAPISpec(Resource):
    def get(self):
        return send_from_directory("docs", "dams-storage-api.json")
