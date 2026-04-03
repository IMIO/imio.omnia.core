# -*- coding: utf-8 -*-
import hashlib
import hmac
import unittest
from unittest.mock import patch

from imio.omnia.core.tokens import generate_token
from imio.omnia.core.tokens import validate_token


class FakeKeyManager:
    def __init__(self, current_secret, ring=None):
        self.current_secret = current_secret
        self.ring = ring if ring is not None else [current_secret]

    def secret(self, name):
        return self.current_secret

    def __getitem__(self, name):
        return self.ring


class TestTokens(unittest.TestCase):
    portal_url = "https://example.com/Plone"

    def _signature(self, secret, portal_url, timestamp):
        return hmac.new(
            secret.encode("utf-8"),
            "{}:{}".format(portal_url, timestamp).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    @patch("imio.omnia.core.tokens.time.time", return_value=1712052000)
    @patch(
        "imio.omnia.core.tokens.getUtility",
        return_value=FakeKeyManager("top-secret"),
    )
    def test_generate_token_uses_timestamp_and_portal_url(self, mock_utility, mock_time):
        token = generate_token(self.portal_url)

        timestamp, signature = token.split(":")
        self.assertEqual(timestamp, "1712052000")
        self.assertEqual(
            signature,
            self._signature("top-secret", self.portal_url, timestamp),
        )
        mock_utility.assert_called_once()
        mock_time.assert_called_once()

    @patch("imio.omnia.core.tokens.time.time", return_value=1712052001)
    @patch(
        "imio.omnia.core.tokens.getUtility",
        return_value=FakeKeyManager("top-secret", ring=["top-secret"]),
    )
    def test_validate_token_accepts_current_token(self, _mock_utility, _mock_time):
        timestamp = "1712052000"
        token = "{}:{}".format(
            timestamp,
            self._signature("top-secret", self.portal_url, timestamp),
        )

        self.assertTrue(validate_token(token, self.portal_url))

    def test_validate_token_rejects_malformed_token(self):
        self.assertFalse(validate_token("bad-token", self.portal_url))

    @patch("imio.omnia.core.tokens.time.time", return_value=1712060000)
    @patch(
        "imio.omnia.core.tokens.getUtility",
        return_value=FakeKeyManager("top-secret", ring=["top-secret"]),
    )
    def test_validate_token_rejects_expired_token(self, _mock_utility, _mock_time):
        timestamp = "1712052000"
        token = "{}:{}".format(
            timestamp,
            self._signature("top-secret", self.portal_url, timestamp),
        )

        self.assertFalse(validate_token(token, self.portal_url, max_age=60))

    @patch("imio.omnia.core.tokens.time.time", return_value=1712052001)
    @patch(
        "imio.omnia.core.tokens.getUtility",
        return_value=FakeKeyManager("top-secret", ring=["top-secret"]),
    )
    def test_validate_token_rejects_wrong_portal_url(self, _mock_utility, _mock_time):
        timestamp = "1712052000"
        token = "{}:{}".format(
            timestamp,
            self._signature("top-secret", self.portal_url, timestamp),
        )

        self.assertFalse(validate_token(token, "https://example.com/Other"))

    @patch("imio.omnia.core.tokens.time.time", return_value=1712052001)
    @patch(
        "imio.omnia.core.tokens.getUtility",
        return_value=FakeKeyManager(
            "current-secret",
            ring=[None, "old-secret", "rotated-secret"],
        ),
    )
    def test_validate_token_accepts_any_secret_in_ring(self, _mock_utility, _mock_time):
        timestamp = "1712052000"
        token = "{}:{}".format(
            timestamp,
            self._signature("rotated-secret", self.portal_url, timestamp),
        )

        self.assertTrue(validate_token(token, self.portal_url))
