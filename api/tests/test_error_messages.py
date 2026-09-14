import os
import unittest
from unittest.mock import patch

from app import app
from requests.exceptions import InvalidHeader
from resources.base_resource import BaseResource, client_error_message
from storage_exceptions import ExpiredTicketException

TOKEN = "eyJhbGciOiJSUzI1NiJ9.cGF5bG9hZA.c2lnbmF0dXJl"


class ErrorMessageTest(unittest.TestCase):
    def test_auth_header_strips_whitespace_from_static_jwt(self):
        with patch.dict(os.environ, {"STATIC_JWT": f"{TOKEN}\n"}):
            with app.test_request_context("/upload"):
                headers = BaseResource().session.headers

        self.assertEqual(f"Bearer {TOKEN}", headers["Authorization"])

    def test_unexpected_exception_message_is_generic(self):
        message = client_error_message(
            InvalidHeader(f"Invalid ... in header value: 'Bearer {TOKEN}'"),
        )

        self.assertNotIn(TOKEN, message)

    def test_known_exception_message_is_kept(self):
        self.assertEqual(
            "Ticket is expired",
            client_error_message(ExpiredTicketException("Ticket is expired")),
        )
