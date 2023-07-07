import app
import json
import mimetypes


class DuplicateFileException(Exception):
    def __init__(self, message, filename=None, md5sum=None):
        super().__init__(message)
        self.message = message
        self.filename = filename
        self.md5sum = md5sum


class FileNotFoundException(Exception):
    pass


class MediafileNotFoundException(Exception):
    pass


def get_mimetype_from_filename(filename):
    mime = mimetypes.guess_type(filename, False)[0]
    return mime if mime else "application/octet-stream"


def read_json_as_dict(filename):
    try:
        with open(filename) as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError) as ex:
        app.logger.error(f"Could not read {filename} as a dict: {ex}")
    return {}
