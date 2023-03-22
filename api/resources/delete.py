from app import policy_factory, logger
from flask import request
from flask_restful import abort
from inuits_policy_based_auth import RequestContext
from resources.base_resource import BaseResource


class Delete(BaseResource):
    @policy_factory.apply_policies(RequestContext(request, ["delete-file"]))
    def delete(self, key):
        try:
            self.storage.delete_files([key])
        except Exception as ex:
            logger.error(f"Deleting {key} failed with: {ex}")
            return str(ex), 400
        return "", 204


class DeleteMultiple(BaseResource):
    def __get_request_body(self):
        if request_body := request.get_json(silent=True):
            return request_body
        abort(405, message="Invalid input")

    @policy_factory.apply_policies(RequestContext(request, ["delete-file-multiple"]))
    def delete(self):
        files = self.__get_request_body()
        try:
            self.storage.delete_files(files)
        except Exception as ex:
            logger.error(f"Deleting {files} failed with: {ex}")
            return str(ex), 400
        return "", 204
