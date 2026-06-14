from django.test import TestCase
from esi.errors import TokenError
from esi.models import Token

from blueprints.decorators import fetch_token_for_owner
from blueprints.tests.helpers import extract
from blueprints.tests.testdata.factory import OwnerCorporationFactory

DUMMY_URL = "http://www.example.com"


class TestFetchToken(TestCase):
    def test_specified_scope(self):
        @fetch_token_for_owner("esi-corporations.read_blueprints.v1")
        def dummy(owner, token: Token):
            self.assertIsInstance(token, Token)
            self.assertIn(
                "esi-corporations.read_blueprints.v1", extract(token.scopes, "name")
            )

        owner = OwnerCorporationFactory()
        dummy(owner)

    def test_exceptions_if_not_found(self):
        @fetch_token_for_owner("invalid_scope")
        def dummy(owner, token):
            pass

        owner = OwnerCorporationFactory()
        with self.assertRaises(TokenError):
            dummy(owner)
