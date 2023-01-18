class DuplicateFileException(Exception):
    def __init__(self, message, filename=None, md5sum=None):
        super().__init__(message)
        self.message = message
        self.filename = filename
        self.md5sum = md5sum


class MediafileNotFoundException(Exception):
    pass
