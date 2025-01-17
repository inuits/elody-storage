import json
import logging
import os
import secrets

from elody.loader import load_apps, load_policies
from flask import Flask
from flask_cors import CORS
from flask_restful import Api
from flask_swagger_ui import get_swaggerui_blueprint
from healthcheck import HealthCheck
from importlib import import_module
from inuits_policy_based_auth.policy_factory import PolicyFactory
from rabbitmq_pika_flask import RabbitMQ
from rabbitmq_pika_flask.ExchangeParams import ExchangeParams
from storage.storagemanager import StorageManager

if os.getenv("SENTRY_ENABLED", False) in ["True", "true", True]:
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration

    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        integrations=[FlaskIntegration()],
        environment=os.getenv("NOMAD_NAMESPACE"),
    )

SWAGGER_URL = "/api/docs"  # URL for exposing Swagger UI (without trailing '/')
API_URL = (
    "/spec/dams-storage-api.json"  # Our API url (can of course be a local resource)
)

swaggerui_blueprint = get_swaggerui_blueprint(SWAGGER_URL, API_URL)

app = Flask(__name__)
api = Api(app)
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(16))
cors = CORS(app, origins=[str(os.getenv("DAMS_FRONTEND_URL"))])

logging.basicConfig(
    format="%(asctime)s %(process)d,%(threadName)s %(filename)s:%(lineno)d [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

rabbit = RabbitMQ(
    exchange_params=ExchangeParams(
        passive=os.getenv("PASSIVE_EXCHANGE", False)
        in [
            1,
            "1",
            "True",
            "true",
            True,
        ],
        durable=os.getenv("DURABLE_EXCHANGE", False)
        in [
            1,
            "1",
            "True",
            "true",
            True,
        ],
    )
)
rabbit.init_app(app, "basic", json.loads, json.dumps)

app.register_blueprint(swaggerui_blueprint)


def rabbit_available():
    connection = rabbit.get_connection()
    if connection.is_open:
        connection.close()
        return True, "Successfully reached RabbitMQ"
    return False, "Failed to reach RabbitMQ"


def storage_available():
    return True, StorageManager().get_storage_engine().check_health()


health = HealthCheck()
if os.getenv("HEALTH_CHECK_EXTERNAL_SERVICES", True) in ["True", "true", True]:
    health.add_check(rabbit_available)
    health.add_check(storage_available)
app.add_url_rule("/health", "healthcheck", view_func=lambda: health.run())

policy_factory = PolicyFactory()
load_apps(app, logger)
try:
    module = import_module("apps.permissions")
    load_policies(policy_factory, logger, module.PERMISSIONS)
except ModuleNotFoundError:
    load_policies(policy_factory, logger)

from resources.download import Download, DownloadWithTicket
from resources.unique import Unique
from resources.upload import (
    Upload,
    UploadWithTicket,
    UploadKey,
    UploadKeyWithTicket,
    UploadTranscode,
)
from resources.spec import AsyncAPISpec, OpenAPISpec
import resources.queues

if os.getenv("ENABLE_DELETE"):
    from resources.delete import Delete, DeleteMultiple

    api.add_resource(Delete, "/delete/<string:key>")
    api.add_resource(DeleteMultiple, "/delete")

api.add_resource(Download, "/download/<string:key>")
api.add_resource(DownloadWithTicket, "/download-with-ticket/<string:key>")

api.add_resource(Unique, "/unique/<string:md5sum>")

api.add_resource(Upload, "/upload")
api.add_resource(UploadWithTicket, "/upload-with-ticket")
api.add_resource(UploadKey, "/upload/<string:key>")
api.add_resource(UploadKeyWithTicket, "/upload-with-ticket/<string:key>")
api.add_resource(UploadTranscode, "/upload/transcode")

api.add_resource(AsyncAPISpec, "/spec/dams-csv-importer-events.html")
api.add_resource(OpenAPISpec, "/spec/dams-storage-api.json")

if __name__ == "__main__":
    app.run()
