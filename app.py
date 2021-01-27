from flask import Flask
from flask_restful import Api
from resources.upload import Upload
from resources.download import Download


app = Flask(__name__)

api = Api(app)

api.add_resource(Upload, '/upload')
api.add_resource(Download, '/download/<string:filename>')

if __name__ == '__main__':
    app.run(debug=True)
