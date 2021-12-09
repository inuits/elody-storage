import app
import os

from flask import request
from flask_restful import Resource
from job_helper.job_helper import JobHelper
from storage.storage import upload_file

job_helper = JobHelper(
    job_api_base_url=os.getenv("JOB_API_BASE_URL", "http://localhost:8000"),
    static_jwt=os.getenv("STATIC_JWT", False),
)


def _get_mediafile_id(req):
    return req.args.get("id")


class Upload(Resource):
    @app.require_oauth()
    def post(self):
        job = job_helper.create_new_job("Upload file", "file_upload")
        job_helper.progress_job(job)
        try:
            file = request.files["file"]
            mediafile_id = _get_mediafile_id(request)
            upload_file(file, mediafile_id)
            job_helper.finish_job(job)
        except Exception as ex:
            job_helper.fail_job(job, str(ex))
            return str(ex), 400
        return "", 201


class UploadKey(Resource):
    @app.require_oauth()
    def post(self, key):
        job = job_helper.create_new_job("Upload file", "file_upload")
        job_helper.progress_job(job)
        try:
            file = request.files["file"]
            mediafile_id = _get_mediafile_id(request)
            upload_file(file, mediafile_id, key)
            job_helper.finish_job(job)
        except Exception as ex:
            job_helper.fail_job(job, str(ex))
            return str(ex), 400
        return "", 201
