import os
from flask import Flask
from flask_restful import Api
from flask_restful_swagger import swagger
from flask_oidc import OpenIDConnect

app = Flask(__name__)

api = swagger.docs(
    Api(app),
    apiVersion="0.1",
    basePath="http://localhost:8001",
    resourcePath="/",
    produces=["application/json", "text/html"],
    api_spec_url="/api/spec",
    description="The DAMS storage API",
)

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

oidc = OpenIDConnect(app)

from resources.upload import Upload, UploadKey
from resources.download import Download

api.add_resource(Upload, "/upload")
api.add_resource(UploadKey, "/upload/<string:key>")
api.add_resource(Download, "/download/<string:key>")

if __name__ == "__main__":
    app.run(debug=True)
