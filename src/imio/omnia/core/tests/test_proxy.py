# -*- coding: utf-8 -*-
"""Tests for OmniaProxyView."""
import json
import unittest
from unittest.mock import MagicMock, patch

import httpx2
from plone import api
from plone.app.testing import TEST_USER_ID, setRoles
from zope.component import ComponentLookupError, getMultiAdapter
from zope.interface import alsoProvides
from zope.publisher.browser import TestRequest

from imio.omnia.core import oauth
from imio.omnia.core.browser.proxy import OmniaOpenAIProxyView
from imio.omnia.core.browser.proxy import OmniaProxyView
from imio.omnia.core.browser.proxy import SSEStreamIterator
from imio.omnia.core.interfaces import IImioOmniaCoreLayer
from imio.omnia.core.settings import get_enable_proxy, set_enable_proxy
from imio.omnia.core.settings import set_core_auth_type
from imio.omnia.core.settings import set_openai_auth_type
from imio.omnia.core.settings import set_enable_openai_proxy
from imio.omnia.core.settings import set_openai_api_url
from imio.omnia.core.settings import set_setting
from imio.omnia.core.testing import IMIO_OMNIA_CORE_INTEGRATION_TESTING
from imio.omnia.core.tokens import generate_token


class TestOmniaProxyView(unittest.TestCase):
    """Tests for OmniaProxyView — security gates and behavior.

    Security gates:
      1. Browser layer (IImioOmniaCoreLayer): view only exists when the add-on
         is installed and the layer is active on the request.
      2. ``enable_proxy`` registry flag: defaults to False; only a Manager can
         enable it via the control panel.
      3. Dedicated browser view permission: access policy is declared in ZCML
         and GenericSetup instead of being hard-coded in Python.

    Only ``httpx2.request`` is mocked for upstream tests; all Plone machinery
    (registry, component lookup, adapters) runs for real.
    """

    layer = IMIO_OMNIA_CORE_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.request = self.layer["request"]
        alsoProvides(self.request, IImioOmniaCoreLayer)
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        set_enable_proxy(False)
        # These tests mock httpx2.request directly (plain transport); the
        # default core_auth_type is now oauth2, so pin it back to
        # "none" here to keep exercising that path.
        set_core_auth_type("none")

    def _get_view(self, body=b"", path_segments=None):
        """Instantiate OmniaProxyView directly, bypassing ZPublisher."""
        self.request.BODY = (
            json.dumps(body).encode() if isinstance(body, dict) else
            body.encode() if isinstance(body, str) else body
        )
        view = OmniaProxyView(self.portal, self.request)
        for segment in path_segments or []:
            view.publishTraverse(self.request, segment)
        return view

    # --- ZCML registration / browser layer ---

    def test_view_reachable_with_browser_layer(self):
        """OmniaProxyView is resolved by getMultiAdapter when layer is active."""
        view = getMultiAdapter((self.portal, self.request), name="omnia-api")
        self.assertIsInstance(view, OmniaProxyView)

    def test_view_not_reachable_without_browser_layer(self):
        """Without IImioOmniaCoreLayer on the request, omnia-api is not registered."""
        bare_request = TestRequest(environ={"REQUEST_METHOD": "GET"})
        with self.assertRaises(ComponentLookupError):
            getMultiAdapter((self.portal, bare_request), name="omnia-api")

    # --- enable_proxy flag (primary security gate) ---

    def test_proxy_disabled_by_default(self):
        """enable_proxy registry flag defaults to False."""
        self.assertFalse(get_enable_proxy())

    def test_proxy_disabled_returns_404_for_manager(self):
        """View returns 404 when proxy is disabled, even for a Manager."""
        view = self._get_view(body={})
        result = json.loads(view())
        self.assertEqual(self.request.response.getStatus(), 404)
        self.assertEqual(result, {"error": "Not found"})

    def test_proxy_disabled_returns_404_for_member(self):
        """View returns 404 when proxy is disabled for regular members."""
        setRoles(self.portal, TEST_USER_ID, ["Member"])
        self._get_view(body={})()
        self.assertEqual(self.request.response.getStatus(), 404)

    def test_response_content_type_always_json(self):
        """Content-Type is always application/json, even when proxy is disabled."""
        self._get_view(body={})()
        self.assertEqual(
            self.request.response.getHeader("Content-Type"), "application/json"
        )

    # --- publishTraverse ---

    def test_publish_traverse_accumulates_segments(self):
        """Each publishTraverse call appends a segment; order is preserved."""
        view = OmniaProxyView(self.portal, self.request)
        view.publishTraverse(self.request, "v1")
        view.publishTraverse(self.request, "agents")
        view.publishTraverse(self.request, "improve-text")
        self.assertEqual(view._path_segments, ["v1", "agents", "improve-text"])

    def test_publish_traverse_returns_self(self):
        """publishTraverse returns the view itself to support chained traversal."""
        view = OmniaProxyView(self.portal, self.request)
        self.assertIs(view.publishTraverse(self.request, "v1"), view)

    # --- Body parsing ---

    def test_invalid_json_body_returns_400(self):
        """Malformed JSON in request body returns 400 with error message."""
        set_enable_proxy(True)
        result = json.loads(self._get_view(body="not {valid} json")())
        self.assertEqual(self.request.response.getStatus(), 400)
        self.assertEqual(result, {"error": "Invalid JSON body"})

    def test_empty_body_returns_400(self):
        """An empty request body (not parseable as JSON) returns 400."""
        set_enable_proxy(True)
        json.loads(self._get_view(body="")())
        self.assertEqual(self.request.response.getStatus(), 400)

    # --- Upstream service integration ---

    @patch("httpx2.request")
    def test_successful_call_returns_upstream_json(self, mock_httpx):
        """On a successful upstream call, the JSON result is passed through."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"output": "improved text"}
        mock_resp.raise_for_status.return_value = None
        mock_httpx.return_value = mock_resp

        set_enable_proxy(True)
        result = json.loads(self._get_view(
            body={"input": "some text"},
            path_segments=["v1", "agents", "improve-text"],
        )())
        self.assertEqual(result, {"output": "improved text"})
        self.assertEqual(self.request.response.getStatus(), 200)

    @patch("httpx2.request")
    def test_upstream_http_error_forwards_status_code(self, mock_httpx):
        """An HTTPStatusError from upstream is forwarded as-is."""
        upstream_response = MagicMock()
        upstream_response.status_code = 422
        mock_httpx.side_effect = httpx2.HTTPStatusError(
            "Unprocessable Entity",
            request=MagicMock(),
            response=upstream_response,
        )

        set_enable_proxy(True)
        result = json.loads(self._get_view(
            body={"input": "text"},
            path_segments=["v1", "agents", "improve-text"],
        )())
        self.assertEqual(self.request.response.getStatus(), 422)
        self.assertIn("error", result)

    @patch("httpx2.request")
    def test_generic_exception_returns_502(self, mock_httpx):
        """An unexpected exception from the service layer returns 502."""
        mock_httpx.side_effect = ConnectionError("upstream unreachable")

        set_enable_proxy(True)
        result = json.loads(self._get_view(
            body={"input": "text"},
            path_segments=["v1", "agents", "improve-text"],
        )())
        self.assertEqual(self.request.response.getStatus(), 502)
        self.assertEqual(result, {"error": "Upstream API error"})

    @patch("httpx2.request")
    def test_path_segments_included_in_upstream_url(self, mock_httpx):
        """The assembled path is sent to the upstream service URL."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status.return_value = None
        mock_httpx.return_value = mock_resp

        set_enable_proxy(True)
        self._get_view(
            body={"input": "text"},
            path_segments=["v1", "agents", "correct-text"],
        )()
        # httpx2.request(method, url, ...) — url is the second positional arg.
        self.assertIn("/v1/agents/correct-text", mock_httpx.call_args[0][1])

    @patch("httpx2.request")
    def test_request_body_forwarded_to_upstream(self, mock_httpx):
        """The parsed JSON body is forwarded verbatim to the upstream service."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status.return_value = None
        mock_httpx.return_value = mock_resp

        set_enable_proxy(True)
        payload = {"input": "bonjour", "target_language": "fr"}
        self._get_view(
            body=payload,
            path_segments=["v1", "agents", "translate-text"],
        )()
        self.assertEqual(mock_httpx.call_args[1].get("json"), payload)


class TestSSEStreamIteratorOwnership(unittest.TestCase):
    """SSEStreamIterator must never close a client it doesn't own (the
    shared OAuth2 client is a process-level singleton — see oauth.py)."""

    def _iterator(self, owns_client):
        client = MagicMock()
        response = MagicMock()
        response.iter_bytes.return_value = iter([b"data: {}\n\n"])
        return SSEStreamIterator(client, response, owns_client=owns_client), client, response

    def test_owned_client_is_closed(self):
        iterator, client, response = self._iterator(owns_client=True)

        list(iterator)

        response.close.assert_called_once()
        client.close.assert_called_once()

    def test_shared_client_is_not_closed(self):
        iterator, client, response = self._iterator(owns_client=False)

        list(iterator)

        response.close.assert_called_once()
        client.close.assert_not_called()


class TestOpenAIProxyOAuthMode(unittest.TestCase):
    """OmniaOpenAIProxyView must route upstream calls through the shared
    OAuth2 client when openai_auth_type=oauth2, and must never close it."""

    layer = IMIO_OMNIA_CORE_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.request = self.layer["request"]
        alsoProvides(self.request, IImioOmniaCoreLayer)
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        set_enable_openai_proxy(True)
        set_openai_api_url("https://ipa.imio.be/imio/omnia/llm/gateway/v1")
        set_openai_auth_type("oauth2")
        for field, value in [
            ("oauth_grant_type", "password"),
            ("oauth_client_id", "cid"),
            ("oauth_client_secret", "sec"),
            ("oauth_token_url", "https://kc.example/token"),
            ("oauth_scope", ""),
            ("oauth_client_auth_method", "client_secret_basic"),
            ("oauth_username", "svc"),
            ("oauth_password", "pw"),
        ]:
            set_setting(field, value)
        oauth.reset_oauth_client()

        portal_url = api.portal.get().absolute_url()
        self.request._auth = "Bearer %s" % generate_token(portal_url)

    def tearDown(self):
        oauth.reset_oauth_client()
        set_openai_auth_type("api_key")
        set_enable_openai_proxy(False)

    def _get_view(self, body, path_segments=None):
        """Instantiate OmniaOpenAIProxyView directly, bypassing ZPublisher."""
        self.request.BODY = json.dumps(body).encode()
        view = OmniaOpenAIProxyView(self.portal, self.request)
        for segment in path_segments or []:
            view.publishTraverse(self.request, segment)
        return view

    @patch("imio.omnia.core.browser.proxy.httpx2.request")
    def test_json_response_routes_through_oauth_client(self, mock_httpx_request):
        """Non-streaming proxy calls go through the shared OAuth2 client,
        not the raw (unauthenticated in oauth mode) httpx2.request()."""
        fake_client = MagicMock()
        fake_resp = MagicMock(status_code=200, text='{"ok": true}')
        fake_client.request.return_value = fake_resp

        with patch("imio.omnia.core.browser.proxy.oauth.get_oauth_client", return_value=fake_client):
            result = self._get_view(
                body={"model": "m", "messages": [], "stream": False},
                path_segments=["chat", "completions"],
            )()

        self.assertEqual(json.loads(result), {"ok": True})
        self.assertEqual(self.request.response.getStatus(), 200)
        fake_client.request.assert_called_once()
        mock_httpx_request.assert_not_called()

    @patch("imio.omnia.core.browser.proxy.httpx2.Client")
    def test_stream_response_uses_shared_client_without_closing_it(self, mock_httpx_client_cls):
        """Streaming proxy calls go through the shared OAuth2 client, with
        its token auth passed explicitly, and never close that client."""
        fake_client = MagicMock()
        fake_upstream = MagicMock()
        fake_upstream.raise_for_status.return_value = None
        fake_client.send.return_value = fake_upstream

        with patch("imio.omnia.core.browser.proxy.oauth.get_oauth_client", return_value=fake_client):
            result = self._get_view(
                body={"model": "m", "messages": [], "stream": True},
                path_segments=["chat", "completions"],
            )()

        self.assertIsInstance(result, SSEStreamIterator)
        self.assertFalse(result._owns_client)
        fake_client.send.assert_called_once()
        self.assertEqual(fake_client.send.call_args.kwargs.get("auth"), fake_client.token_auth)
        fake_client.close.assert_not_called()
        mock_httpx_client_cls.assert_not_called()

    def test_stream_response_returns_502_when_oauth_client_unavailable(self):
        """If obtaining the shared OAuth2 client itself fails (incomplete
        config or the token endpoint rejecting/unreachable), the streaming
        proxy must still degrade to a clean 502 JSON response instead of
        letting the exception escape after SSE headers were set."""
        from authlib.integrations.base_client import OAuthError

        with patch(
            "imio.omnia.core.browser.proxy.oauth.get_oauth_client",
            side_effect=OAuthError("temporarily_unavailable", "kc down"),
        ):
            result = self._get_view(
                body={"model": "m", "messages": [], "stream": True},
                path_segments=["chat", "completions"],
            )()

        self.assertEqual(self.request.response.getStatus(), 502)
        self.assertIn("error", json.loads(result))
        self.assertEqual(self.request.response.getHeader("Content-Type"), "application/json")
