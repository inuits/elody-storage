import os

from elody.util import Singleton
from storage.s3store import S3StorageManager


class StorageManager(metaclass=Singleton):
    def __init__(self):
        self.storage_engine = os.getenv("STORAGE_ENGINE", "s3")
        self.__init_storage_managers()

    def __init_storage_managers(self):
        if self.storage_engine == "s3":
            self.storage_manager = S3StorageManager()

    def get_storage_engine(self, headers=None):
        if headers:
            self.storage_manager.set_headers(headers)
        return self.storage_manager
