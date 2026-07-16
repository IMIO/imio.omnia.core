# -*- coding: utf-8 -*-
import time
import unittest

import httpx2

from imio.omnia.core.oauth import OAuth2Client

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
