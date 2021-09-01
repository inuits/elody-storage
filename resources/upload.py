import os
from flask_restful import Resource
from flask import g, request

from storage.storage import upload_file
from classes.job_helper import JobHelper

import app

token_required = os.getenv("REQUIRE_TOKEN", "True").lower() in ["true", "1"]
job_helper = JobHelper(os.getenv("JOB_API_BASE_URL", "http://localhost:8000"))


class Upload(Resource):
    @app.oidc.accept_token(require_token=token_required, scopes_required=["openid"])
    def post(self):
        user = g.oidc_token_info["email"] if hasattr(g, "oidc_token_info") else "default_uploader"
        job = job_helper.create_new_job("Upload file", "file_upload", user=user)
        job_helper.progress_job(job)
        try:
            f = request.files["file"]
            upload_file(f)
            job_helper.finish_job(job)
        except:
            job_helper.fail_job(job, sys.exc_info()[0])
        return "", 201


class UploadKey(Resource):
    @app.oidc.accept_token(require_token=token_required, scopes_required=["openid"])
    def post(self, key):
        user = g.oidc_token_info["email"] if hasattr(g, "oidc_token_info") else "default_uploader"
        job = job_helper.create_new_job("Upload file", "file_upload", user=user)
        job_helper.progress_job(job)
        try:
            f = request.files["file"]
            upload_file(f, key)
            job_helper.finish_job(job)
        except:
            job_helper.fail_job(job, sys.exc_info()[0])
        return "", 201
