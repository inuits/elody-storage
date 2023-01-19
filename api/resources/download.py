import app
import re
import util

from flask import request, Response, stream_with_context
from flask_restful import abort
from resources.base_resource import BaseResource
from werkzeug.datastructures import Headers


class Download(BaseResource):
    def __get_byte_range(self, range_header):
        g = re.search("(\d+)-(\d*)", range_header).groups()
        byte1, byte2, length = 0, None, None
        if g[0]:
            byte1 = int(g[0])
        if g[1]:
            byte2 = int(g[1])
            length = byte2 + 1 - byte1
        return byte1, byte2, length

    @app.require_oauth("download-file")
    def get(self, key):
        chunk = False
        try:
            file_object = self.storage.download_file(key)
        except util.FileNotFoundException as ex:
            abort(404, message=str(ex))
        content_type = util.get_mimetype_from_filename(key)
        full_length = file_object["content_length"]
        headers = Headers()
        headers["Accept-Ranges"] = "bytes"
        headers["Content-Type"] = content_type
        headers["Content-Length"] = full_length
        if range_header := request.headers.get("Range"):
            byte_start, byte_end, length = self.__get_byte_range(range_header)
            if byte_end:
                chunk = True
                file_object = self.storage.download_file(
                    key, f"bytes={byte_start}-{byte_end}"
                )
                end = byte_start + length - 1
                headers["Content-Range"] = f"bytes {byte_start}-{end}/{full_length}"
                headers["Content-Transfer-Encoding"] = "binary"
                headers["Connection"] = "Keep-Alive"
                headers["Content-Type"] = content_type
                headers["Content-Length"] = file_object["content_length"]
                if byte_end == 1:
                    headers["Content-Length"] = "1"
        response = Response(
            stream_with_context(
                self.storage.get_stream_generator(file_object["stream"])
            ),
            mimetype=content_type,
            content_type=content_type,
            headers=headers,
            status=206 if chunk else 200,
            direct_passthrough=chunk,
        )
        return response
