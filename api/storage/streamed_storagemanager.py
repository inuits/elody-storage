from os import getenv

from elody.util import Singleton
from storage.streamed_s3store import StreamedS3Store


class StreamedStorageManager(metaclass=Singleton):
    def __init__(self):
        self.storage_engine = getenv("STORAGE_ENGINE", "s3")
        self.__init_stores()

    def __init_stores(self):
        if self.storage_engine == "s3":
            self.store = StreamedS3Store()

    def get_storage_engine(self):
        return self.store
