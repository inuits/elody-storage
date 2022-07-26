from exceptions import MediafileNotFoundException
from flask_restful import Resource
from storage.storagemanager import StorageManager


class BaseResource(Resource):
    def __init__(self):
        self.storage = StorageManager().get_storage_engine()

    def _get_mediafile_id(self, req):
        if mediafile_id := req.args.get("id"):
            return mediafile_id
        raise MediafileNotFoundException("No mediafile id provided")
