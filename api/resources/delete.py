import app

from flask import request
from flask_restful import abort
from resources.base_resource import BaseResource
from werkzeug.exceptions import BadRequest


class Delete(BaseResource):
    @app.require_oauth("delete-file")
    def delete(self, key):
        try:
            self.storage.delete_files([key])
        except Exception as ex:
            app.logger.error(f"Deleting {key} failed with: {ex}")
            return str(ex), 400
        return "", 204


class DeleteMultiple(BaseResource):
    def __get_request_body(self):
        try:
            request_body = request.get_json()
            invalid_input = request_body is None
        except BadRequest:
            invalid_input = True
        if invalid_input:
            abort(405, message="Invalid input")
        return request_body

    @app.require_oauth("delete-file-multiple")
    def delete(self):
        files = self.__get_request_body()
        try:
            self.storage.delete_files(files)
        except Exception as ex:
            app.logger.error(f"Deleting {files} failed with: {ex}")
            return str(ex), 400
        return "", 204
