from flask_restful import Resource
from storage.storagemanager import StorageManager


class BaseResource(Resource):
    def __init__(self):
        self.storage = StorageManager().get_storage_engine()
