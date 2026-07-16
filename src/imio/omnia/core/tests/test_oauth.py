# -*- coding: utf-8 -*-
import time
import unittest
from unittest.mock import patch

import httpx2
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID

from imio.omnia.core import oauth
from imio.omnia.core.oauth import OAuth2Client
from imio.omnia.core.settings import set_setting
from imio.omnia.core.testing import IMIO_OMNIA_CORE_INTEGRATION_TESTING

TOKEN_URL = "https://kc.example/realms/sso-apps/protocol/openid-connect/token"


def token_response(access_token="tok-1"):
    return httpx2.Response(
        200,
        json={
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 300,
            "refresh_token": "ref-1",
        },
    )


class TestOAuth2ClientPort(unittest.TestCase):
    """The httpx2 port of authlib's sync OAuth2Client."""

    def _client(self, handler, **kwargs):
        kwargs.setdefault("client_id", "cid")
        kwargs.setdefault("client_secret", "sec")
        kwargs.setdefault("token_endpoint_auth_method", "client_secret_basic")
        return OAuth2Client(transport=httpx2.MockTransport(handler), **kwargs)

    def test_fetch_token_password_grant_uses_basic_auth(self):
        seen = []

        def handler(request):
            seen.append(request)
            return token_response()

        client = self._client(handler)
        token = client.fetch_token(TOKEN_URL, grant_type="password", username="svc", password="pw")

        self.assertEqual(token["access_token"], "tok-1")
        request = seen[0]
        self.assertTrue(request.headers["Authorization"].startswith("Basic "))
        body = request.content.decode()
        self.assertIn("grant_type=password", body)
        self.assertIn("username=svc", body)
        self.assertIn("password=pw", body)

    def test_fetch_token_client_secret_post_puts_credentials_in_body(self):
        seen = []

        def handler(request):
            seen.append(request)
            return token_response()

        client = self._client(handler, token_endpoint_auth_method="client_secret_post")
        client.fetch_token(TOKEN_URL, grant_type="client_credentials")

        request = seen[0]
        self.assertNotIn("authorization", request.headers)
        body = request.content.decode()
        self.assertIn("client_id=cid", body)
        self.assertIn("client_secret=sec", body)
        self.assertIn("grant_type=client_credentials", body)

    def test_request_sends_bearer_token(self):
        seen = []

        def handler(request):
            seen.append(request)
            return httpx2.Response(200, json={"ok": True})

        client = self._client(
            handler,
            token={
                "access_token": "tok-1",
                "token_type": "Bearer",
                "expires_at": int(time.time()) + 300,
            },
        )
        response = client.request("GET", "https://api.example/models")

        self.assertEqual(response.json(), {"ok": True})
        self.assertEqual(seen[0].headers["Authorization"], "Bearer tok-1")

    def test_request_without_token_raises_missing_token_error(self):
        from authlib.integrations.base_client import MissingTokenError

        def handler(request):  # pragma: no cover - must not be reached
            raise AssertionError("no request should be sent")

        client = self._client(handler)

        with self.assertRaises(MissingTokenError):
            client.request("GET", "https://api.example/models")


class TestOAuthClientFactory(unittest.TestCase):
    layer = IMIO_OMNIA_CORE_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        set_setting("auth_type", "oauth2")
        set_setting("oauth_grant_type", "password")
        set_setting("oauth_client_id", "cid")
        set_setting("oauth_client_secret", "sec")
        set_setting("oauth_token_url", TOKEN_URL)
        set_setting("oauth_scope", "")
        set_setting("oauth_client_auth_method", "client_secret_basic")
        set_setting("oauth_username", "svc")
        set_setting("oauth_password", "pw")
        oauth.reset_oauth_client()
        self.token_calls = []

    def tearDown(self):
        oauth.reset_oauth_client()
        set_setting("auth_type", "bearer")

    def _handler(self, request):
        self.token_calls.append(request.content.decode())
        return token_response(access_token=f"tok-{len(self.token_calls)}")

    def _patched_build(self, handler=None):
        original = oauth._build_client
        handler = handler or self._handler

        def build(cfg):
            client = original(cfg)
            client._transport = httpx2.MockTransport(handler)
            return client

        return patch.object(oauth, "_build_client", build)

    def test_token_fetched_once_and_cached(self):
        with self._patched_build():
            client1 = oauth.get_oauth_client()
            client2 = oauth.get_oauth_client()

        self.assertIs(client1, client2)
        self.assertEqual(len(self.token_calls), 1)
        self.assertIn("grant_type=password", self.token_calls[0])
        self.assertEqual(client1.token["access_token"], "tok-1")

    def test_client_rebuilt_when_config_changes(self):
        with self._patched_build():
            client1 = oauth.get_oauth_client()
            set_setting("oauth_client_id", "other-cid")
            client2 = oauth.get_oauth_client()

        self.assertIsNot(client1, client2)
        self.assertTrue(client1.is_closed)
        self.assertEqual(len(self.token_calls), 2)

    def test_expired_token_refetched_when_refresh_fails(self):
        def handler(request):
            body = request.content.decode()
            self.token_calls.append(body)
            if "grant_type=refresh_token" in body:
                return httpx2.Response(400, json={"error": "invalid_grant"})
            return token_response(access_token=f"tok-{len(self.token_calls)}")

        with self._patched_build(handler):
            client = oauth.get_oauth_client()
            client.token["expires_at"] = 1
            client = oauth.get_oauth_client()

        self.assertEqual(client.token["access_token"], f"tok-{len(self.token_calls)}")
        self.assertTrue(any("grant_type=refresh_token" in c for c in self.token_calls))
        self.assertIn("grant_type=password", self.token_calls[-1])

    def test_incomplete_config_raises_value_error(self):
        set_setting("oauth_client_id", "")

        with self.assertRaises(ValueError) as ctx:
            oauth.get_oauth_client()

        self.assertIn("oauth_client_id", str(ctx.exception))

    def test_client_credentials_grant_sends_no_user_credentials(self):
        set_setting("oauth_grant_type", "client_credentials")
        set_setting("oauth_username", "")
        set_setting("oauth_password", "")

        with self._patched_build():
            oauth.get_oauth_client()

        self.assertEqual(len(self.token_calls), 1)
        self.assertIn("grant_type=client_credentials", self.token_calls[0])
        self.assertNotIn("username=", self.token_calls[0])

    def test_failed_initial_fetch_retries_cleanly_on_next_call(self):
        state = {"fail": True}

        def handler(request):
            self.token_calls.append(request.content.decode())
            if state["fail"]:
                return httpx2.Response(400, json={"error": "temporarily_unavailable"})
            return token_response(access_token=f"tok-{len(self.token_calls)}")

        from authlib.integrations.base_client import OAuthError

        with self._patched_build(handler):
            with self.assertRaises(OAuthError):
                oauth.get_oauth_client()
            state["fail"] = False
            client = oauth.get_oauth_client()

        self.assertEqual(client.token["access_token"], f"tok-{len(self.token_calls)}")

    def test_token_inside_eager_window_is_refreshed_under_lock(self):
        with self._patched_build():
            client = oauth.get_oauth_client()
            fetches_before = len(self.token_calls)
            # 70s remaining: fresh for the client's own 60s leeway, but
            # inside the eager window (60 + api_timeout=30 => 90s).
            client.token["expires_at"] = int(time.time()) + 70
            client = oauth.get_oauth_client()

        self.assertEqual(len(self.token_calls), fetches_before + 1)
        self.assertFalse(client.token.is_expired(leeway=60))
