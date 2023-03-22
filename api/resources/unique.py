from app import policy_factory
from flask import request
from inuits_policy_based_auth import RequestContext
from resources.base_resource import BaseResource
from util import DuplicateFileException


class Unique(BaseResource):
    @policy_factory.apply_policies(RequestContext(request, ["unique"]))
    def get(self, md5sum):
        try:
            self.storage.check_file_exists("", md5sum)
        except DuplicateFileException as ex:
            return ex.filename, 409
        return "", 200
