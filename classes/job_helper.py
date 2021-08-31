import json
import string
import pika
from datetime import datetime
from enum import Enum

import requests


class Status(Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in-progress"
    FINISHED = "finished"
    FAILED = "failed"


class JobHelper:
    def __init__(self, job_api_base_url, amqp_url, amqp_exchange_name, amqp_queue_name, amqp_routing_key):
        self.job_api_base_url = job_api_base_url
        amqp_connection = pika.BlockingConnection(pika.ConnectionParameters(amqp_url))
        self.amqp_channel = amqp_connection.channel()
        self.amqp_channel.queue_declare(queue=amqp_queue_name)
        self.amqp_exchange_name = amqp_exchange_name
        self.amqp_routing_key = amqp_routing_key

    def __patch_job(self, job):
        return requests.patch(
            "{}/jobs/{}".format(self.job_api_base_url, job["_id"]), json=job
        ).json()

    def create_new_job(self, job_info: string, job_type: string, user: string, asset_id=None, mediafile_id=None, parent_job_id=None):
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

    def finish_job(self, job, message=""):
        job["status"] = Status.FINISHED.value
        job["end_time"] = str(datetime.utcnow())
        self.amqp_channel.basic_publish(
            exchange=self.amqp_exchange_name,
            routing_key=self.amqp_routing_key,
            body=bytes("Job with id {} finished: {}".format(job["_id"], message))
        )
        return self.__patch_job(job)

    def fail_job(self, job, error_message=""):
        job["status"] = Status.FAILED.value
        job["end_time"] = str(datetime.utcnow())
        self.amqp_channel.basic_publish(
            exchange=self.amqp_exchange_name,
            routing_key=self.amqp_routing_key,
            body=bytes("Job with id {} failed: {}".format(job["_id"], message))
        )
        return self.__patch_job(job)
