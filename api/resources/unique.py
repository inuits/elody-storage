from app import policy_factory
from elody.exceptions import DuplicateFileException
from resources.base_resource import BaseResource


class Unique(BaseResource):
    @policy_factory.authenticate()
    def get(self, md5sum):
        try:
            self.storage.check_file_exists("", md5sum)
        except DuplicateFileException as ex:
            return ex.filename, 409
        return "", 200
