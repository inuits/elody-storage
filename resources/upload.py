import app
import os

from flask import request
from flask_restful import Resource
from job_helper.job_helper import JobHelper
from storage.storage import upload_file

token_required = os.getenv("REQUIRE_TOKEN", "True").lower() in ["true", "1"]
job_helper = JobHelper(os.getenv("JOB_API_BASE_URL", "http://localhost:8000"))


class Upload(Resource):
    @app.oidc.accept_token(require_token=token_required, scopes_required=["openid"])
    def post(self):
        job = job_helper.create_new_job("Upload file", "file_upload")
        job_helper.progress_job(job)
        try:
            f = request.files["file"]
            if request.args.get("action") == "postMD5":
                upload_file(f, url=request.args.get("url"))
            else:
                upload_file(f)
            job_helper.finish_job(job)
        except Exception as ex:
            job_helper.fail_job(job, str(ex))
            return str(ex), 400
        return "", 201


class UploadKey(Resource):
    @app.oidc.accept_token(require_token=token_required, scopes_required=["openid"])
    def post(self, key):
        job = job_helper.create_new_job("Upload file", "file_upload")
        job_helper.progress_job(job)
        try:
            f = request.files["file"]
            if request.args.get("action") == "postMD5":
                upload_file(f, key, request.args.get("url"))
            else:
                upload_file(f)
            job_helper.finish_job(job)
        except Exception as ex:
            job_helper.fail_job(job, str(ex))
            return str(ex), 400
        return "", 201
