# -*- coding: utf-8 -*-
"""Tests for OmniaProxyView."""
import json
import unittest
from unittest.mock import MagicMock, patch

import httpx
from plone.app.testing import TEST_USER_ID, setRoles
from zope.component import ComponentLookupError, getMultiAdapter
from zope.interface import alsoProvides
from zope.publisher.browser import TestRequest

from imio.omnia.core.browser.proxy import OmniaProxyView
from imio.omnia.core.interfaces import IImioOmniaCoreLayer
from imio.omnia.core.settings import get_enable_proxy, set_enable_proxy
from imio.omnia.core.testing import IMIO_OMNIA_CORE_INTEGRATION_TESTING


class TestOmniaProxyView(unittest.TestCase):
    """Tests for OmniaProxyView — security gates and behavior.

    Security gates:
      1. Browser layer (IImioOmniaCoreLayer): view only exists when the add-on
         is installed and the layer is active on the request.
      2. ``enable_proxy`` registry flag: defaults to False; only a Manager can
         enable it via the control panel.
      3. Dedicated browser view permission: access policy is declared in ZCML
         and GenericSetup instead of being hard-coded in Python.

    Only ``httpx.request`` is mocked for upstream tests; all Plone machinery
    (registry, component lookup, adapters) runs for real.
    """

    layer = IMIO_OMNIA_CORE_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.request = self.layer["request"]
        alsoProvides(self.request, IImioOmniaCoreLayer)
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        set_enable_proxy(False)

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

    @patch("httpx.request")
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

    @patch("httpx.request")
    def test_upstream_http_error_forwards_status_code(self, mock_httpx):
        """An HTTPStatusError from upstream is forwarded as-is."""
        upstream_response = MagicMock()
        upstream_response.status_code = 422
        mock_httpx.side_effect = httpx.HTTPStatusError(
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

    @patch("httpx.request")
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

    @patch("httpx.request")
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
        # httpx.request(method, url, ...) — url is the second positional arg.
        self.assertIn("/v1/agents/correct-text", mock_httpx.call_args[0][1])

    @patch("httpx.request")
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
