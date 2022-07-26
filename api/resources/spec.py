from flask import send_from_directory
from resources.base_resource import BaseResource


class OpenAPISpec(BaseResource):
    def get(self):
        return send_from_directory("docs", "dams-storage-api.json")


class AsyncAPISpec(BaseResource):
    def get(self):
        return send_from_directory("docs", "dams-storage-api-events.html")
