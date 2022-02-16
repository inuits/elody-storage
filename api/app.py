import json
import logging
import os

from flask import Flask
from flask_rabmq import RabbitMQ
from flask_restful import Api
from flask_swagger_ui import get_swaggerui_blueprint
from inuits_jwt_auth.authorization import JWTValidator, MyResourceProtector
from job_helper.job_helper import JobHelper


SWAGGER_URL = "/api/docs"  # URL for exposing Swagger UI (without trailing '/')
API_URL = (
    "/spec/dams-storage-api.json"  # Our API url (can of course be a local resource)
)

swaggerui_blueprint = get_swaggerui_blueprint(SWAGGER_URL, API_URL)

app = Flask(__name__)

api = Api(app)

app.config.update(
    {
        "RABMQ_RABBITMQ_URL": os.getenv("RABMQ_RABBITMQ_URL", "amqp://localhost:5672"),
        "RABMQ_SEND_EXCHANGE_NAME": os.getenv("RABMQ_SEND_EXCHANGE_NAME", "dams"),
        "RABMQ_SEND_EXCHANGE_TYPE": "topic",
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
    job_api_base_url=os.getenv("JOB_API_BASE_URL", "http://collection-api:8000"),
    static_jwt=os.getenv("STATIC_JWT", False),
)
"""

ramq = RabbitMQ()
ramq.init_app(app=app)


@ramq.queue(exchange_name="dams", routing_key="dams.file_uploaded")
def handle_file_uploaded(body):
    data = json.loads(body)["data"]
    return True


ramq.run_consumer()

require_oauth = MyResourceProtector(
    os.getenv("STATIC_JWT", False),
    {},
    os.getenv("REQUIRE_TOKEN", True) == ("True" or "true" or True),
)
validator = JWTValidator(
    logger,
    os.getenv("STATIC_JWT", False),
    os.getenv("STATIC_ISSUER", False),
    os.getenv("STATIC_PUBLIC_KEY", False),
    os.getenv("REALMS", "").split(","),
    os.getenv("REQUIRE_TOKEN", True) == ("True" or "true" or True),
)
require_oauth.register_token_validator(validator)

app.register_blueprint(swaggerui_blueprint)

from resources.download import Download
from resources.upload import Upload, UploadKey
from resources.spec import AsyncAPISpec, OpenAPISpec

api.add_resource(Download, "/download/<string:key>")

api.add_resource(Upload, "/upload")
api.add_resource(UploadKey, "/upload/<string:key>")

api.add_resource(AsyncAPISpec, "/spec/dams-csv-importer-events.html")
api.add_resource(OpenAPISpec, "/spec/dams-storage-api.json")

if __name__ == "__main__":
    app.run(debug=True)
