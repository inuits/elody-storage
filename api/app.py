import os
from flask import Flask
from flask_restful import Api
from flask_oidc import OpenIDConnect
from flask_swagger_ui import get_swaggerui_blueprint

app = Flask(__name__)

api = Api(app)

app.config.update(
    {
        "SECRET_KEY": "SomethingNotEntirelySecret",
        "TESTING": True,
        "DEBUG": True,
        "OIDC_CLIENT_SECRETS": "client_secrets.json",
        "OIDC_ID_TOKEN_COOKIE_SECURE": False,
        "OIDC_REQUIRE_VERIFIED_EMAIL": False,
        "OIDC_USER_INFO_ENABLED": True,
        "OIDC_OPENID_REALM": os.getenv("OIDC_OPENID_REALM"),
        "OIDC_SCOPES": ["openid", "email", "profile"],
        "OIDC_INTROSPECTION_AUTH_METHOD": "client_secret_post",
    }
)

SWAGGER_URL = "/api/docs"  # URL for exposing Swagger UI (without trailing '/')
API_URL = (
    "/spec/dams-storage-api.json"  # Our API url (can of course be a local resource)
)

swaggerui_blueprint = get_swaggerui_blueprint(SWAGGER_URL, API_URL)

oidc = OpenIDConnect(app)

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
