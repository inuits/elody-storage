import logging
import os

from flask import Flask
from flask_restful import Api
from flask_oidc import OpenIDConnect
from flask_swagger_ui import get_swaggerui_blueprint

from authorization import MyResourceProtector, JWTValidator

app = Flask(__name__)

api = Api(app)

app.config.update(
    {
        "SECRET_KEY": "SomethingNotEntirelySecret",
        "TESTING": True,
        "DEBUG": True,
    }
)

SWAGGER_URL = "/api/docs"  # URL for exposing Swagger UI (without trailing '/')
API_URL = (
    "/spec/dams-storage-api.json"  # Our API url (can of course be a local resource)
)

swaggerui_blueprint = get_swaggerui_blueprint(SWAGGER_URL, API_URL)

logging.basicConfig(
    format="%(asctime)s %(process)d,%(threadName)s %(filename)s:%(lineno)d [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)
require_oauth = MyResourceProtector(os.getenv("STATIC_JWT", False))
validator = JWTValidator(logger, os.getenv("STATIC_JWT", False), os.getenv("STATIC_ISSUER", False),
                         os.getenv("STATIC_PUBLIC_KEY", False))
require_oauth.register_token_validator(validator)

app.register_blueprint(swaggerui_blueprint)

from resources.upload import Upload, UploadKey
from resources.download import Download
from resources.spec import OpenAPISpec

api.add_resource(Upload, "/upload")
api.add_resource(UploadKey, "/upload/<string:key>")
api.add_resource(Download, "/download/<string:key>")
api.add_resource(OpenAPISpec, "/spec/dams-storage-api.json")


if __name__ == "__main__":
    app.run(debug=True)
