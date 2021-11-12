import app
import os

from flask import request
from flask_restful import abort, Resource
from job_helper.job_helper import JobHelper
from storage.storage import upload_file

token_required = os.getenv("REQUIRE_TOKEN", "True").lower() in ["true", "1"]
job_helper = JobHelper(os.getenv("JOB_API_BASE_URL", "http://localhost:8000"))


class Upload(Resource):
    @app.require_oauth()
    def post(self):
        job = job_helper.create_new_job("Upload file", "file_upload")
        job_helper.progress_job(job)
        try:
            f = request.files["file"]
            url = request.args.get("url")
            if not url:
                abort(400, message="No callback url provided")
            upload_file(f, url)
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
            f = request.files["file"]
            url = request.args.get("url")
            if not url:
                abort(400, message="No callback url provided")
            upload_file(f, url, key)
            job_helper.finish_job(job)
        except Exception as ex:
            job_helper.fail_job(job, str(ex))
            return str(ex), 400
        return "", 201
