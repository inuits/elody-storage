import json
import string
from datetime import datetime
from enum import Enum
import requests


class Status(Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in-progress"
    FINISHED = "finished"
    FAILED = "failed"


class JobHelper:
    def __init__(self, job_api_base_url):
        self.job_api_base_url = job_api_base_url

    def __patch_job(self, job):
        return requests.patch(
            "{}/jobs/{}".format(self.job_api_base_url, job["_id"]), json=job
        ).json()

    def create_new_job(self, job_info: string, job_type: string, user: string, asset_id=None, mediafile_id=None,
                       parent_job_id=None):
        new_job = {
            "job_type": job_type,
            "job_info": job_info,
            "status": Status.QUEUED.value,
            "start_time": str(datetime.utcnow()),
            "user": user,
            "asset_id": "" if asset_id is None else asset_id,
            "mediafile_id": "" if mediafile_id is None else mediafile_id,
            "parent_job_id": "" if parent_job_id is None else parent_job_id
        }
        job = json.loads(requests.post(
            "{}/jobs".format(self.job_api_base_url), json=new_job
        ).text)
        return job

    def progress_job(self, job, asset_id=None, mediafile_id=None, parent_job_id=None):
        job["asset_id"] = "" if asset_id is None else asset_id
        job["mediafile_id"] = "" if mediafile_id is None else mediafile_id
        job["parent_job_id"] = "" if parent_job_id is None else parent_job_id
        job["status"] = Status.IN_PROGRESS.value
        return self.__patch_job(job)

    def finish_job(self, job):
        job["status"] = Status.FINISHED.value
        job["end_time"] = str(datetime.utcnow())
        return self.__patch_job(job)

    def fail_job(self, job):
        job["status"] = Status.FAILED.value
        job["end_time"] = str(datetime.utcnow())
        return self.__patch_job(job)
