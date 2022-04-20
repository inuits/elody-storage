import json
import logging
import os

import requests
from flask import Flask
from flask_restful import Api
from flask_swagger_ui import get_swaggerui_blueprint
from healthcheck import HealthCheck
from inuits_jwt_auth.authorization import JWTValidator, MyResourceProtector
from job_helper.job_helper import JobHelper
from rabbitmq_pika_flask import RabbitMQ
from storage import storage

SWAGGER_URL = "/api/docs"  # URL for exposing Swagger UI (without trailing '/')
API_URL = (
    "/spec/dams-storage-api.json"  # Our API url (can of course be a local resource)
)

swaggerui_blueprint = get_swaggerui_blueprint(SWAGGER_URL, API_URL)

app = Flask(__name__)

api = Api(app)

app.config.update(
    {
        "MQ_EXCHANGE": os.getenv("RABMQ_SEND_EXCHANGE_NAME"),
        "MQ_URL": os.getenv("RABMQ_RABBITMQ_URL"),
        "SECRET_KEY": "SomethingNotEntirelySecret",
        "TESTING": True,
        "DEBUG": True,
    }
)

logging.basicConfig(
    format="%(asctime)s %(process)d,%(threadName)s %(filename)s:%(lineno)d [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)
"""
job_helper = JobHelper(
    job_api_base_url=os.getenv("JOB_API_BASE_URL"),
    static_jwt=os.getenv("STATIC_JWT", False),
)
"""

rabbit = RabbitMQ()
rabbit.init_app(app, "basic", json.loads, json.dumps)


def rabbit_available():
    return True, rabbit.get_connection().is_open


health = HealthCheck()
if os.getenv("HEALTH_CHECK_EXTERNAL_SERVICES", True) in ["True", "true", True]:
    health.add_check(rabbit_available)
app.add_url_rule("/health", "healthcheck", view_func=lambda: health.run())


@rabbit.queue("dams.file_uploaded")
def handle_file_uploaded(routing_key, body, message_id):
    data = body["data"]
    if "mediafile" not in data or "mimetype" not in data or "url" not in data:
        return
    if "metadata" not in data["mediafile"] or not len(data["mediafile"]["metadata"]):
        return
    storage.add_exif_data(data["mediafile"], data["mimetype"])


@rabbit.queue("dams.mediafile_changed")
def handle_mediafile_updated(routing_key, body, message_id):
    data = body["data"]
    if "old_mediafile" not in data or "mediafile" not in data:
        return
    if "metadata" not in data["mediafile"] or not storage.is_metadata_updated(
        data["old_mediafile"]["metadata"], data["mediafile"]["metadata"]
    ):
        return
    storage.add_exif_data(data["mediafile"])


@rabbit.queue("dams.mediafile_deleted")
def handle_mediafile_deleted(routing_key, body, message_id):
    data = body["data"]
    if "mediafile" not in data or "linked_entities" not in data:
        return
    storage.delete_file(data["mediafile"])


require_oauth = MyResourceProtector(
    os.getenv("REQUIRE_TOKEN", True) == ("True" or "true" or True),
)
validator = JWTValidator(
    logger,
    os.getenv("STATIC_ISSUER", False),
    os.getenv("STATIC_PUBLIC_KEY", False),
    os.getenv("REALMS", "").split(","),
    os.getenv("ROLE_PERMISSION_FILE", "role_permission.json"),
    os.getenv("SUPER_ADMIN_ROLE", "role_super_admin"),
    os.getenv("REMOTE_TOKEN_VALIDATION", False),
)
require_oauth.register_token_validator(validator)

app.register_blueprint(swaggerui_blueprint)

from resources.download import Download
from resources.upload import Upload, UploadKey, UploadTranscode
from resources.spec import AsyncAPISpec, OpenAPISpec

api.add_resource(Download, "/download/<string:key>")

api.add_resource(Upload, "/upload")
api.add_resource(UploadKey, "/upload/<string:key>")
api.add_resource(UploadTranscode, "/upload/transcode")

api.add_resource(AsyncAPISpec, "/spec/dams-csv-importer-events.html")
api.add_resource(OpenAPISpec, "/spec/dams-storage-api.json")

if __name__ == "__main__":
    app.run(debug=True)
