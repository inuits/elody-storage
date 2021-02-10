from flask import Flask
from flask_restful import Api
from flask_oidc import OpenIDConnect

app = Flask(__name__)

api = Api(app)

app.config.update({
    'SECRET_KEY': 'SomethingNotEntirelySecret',
    'TESTING': True,
    'DEBUG': True,
    'OIDC_CLIENT_SECRETS': 'client_secrets.json',
    'OIDC_ID_TOKEN_COOKIE_SECURE': False,
    'OIDC_REQUIRE_VERIFIED_EMAIL': False,
    'OIDC_USER_INFO_ENABLED': True,
    'OIDC_OPENID_REALM': 'mediamosa-ng',
    'OIDC_SCOPES': ['openid', 'email', 'profile'],
    'OIDC_INTROSPECTION_AUTH_METHOD': 'client_secret_post'
})

oidc = OpenIDConnect(app)

from resources.upload import Upload
from resources.download import Download

api.add_resource(Upload, '/upload')
api.add_resource(Download, '/download/<string:filename>')

if __name__ == '__main__':
    app.run(debug=True)
