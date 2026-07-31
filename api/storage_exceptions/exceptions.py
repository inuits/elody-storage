class MissingFilenameException(Exception):
    pass


class ExpiredTicketException(Exception):  # Arguably should be in sdk?
    pass


class MissingTicketIdException(Exception):
    pass


class ForbiddenMimetypeException(Exception):
    pass


class MissingBucketnameException(Exception):
    pass
