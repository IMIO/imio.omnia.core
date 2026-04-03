# -*- coding: utf-8 -*-
import json
import logging
from urllib.parse import urlparse

import httpx
from plone import api
from plone.protect.interfaces import IDisableCSRFProtection
from Products.Five import BrowserView
from zope.component import getMultiAdapter
from ZPublisher.Iterators import IUnboundStreamIterator
from zope.interface import alsoProvides
from zope.interface import implementer
from zope.publisher.interfaces import IPublishTraverse

from imio.omnia.core.interfaces import IOmniaOpenAIService
from imio.omnia.core.services import IOmniaCoreAPIService
from imio.omnia.core.settings import get_enable_openai_proxy
from imio.omnia.core.settings import get_enable_proxy
from imio.omnia.core.settings import get_openai_api_url
from imio.omnia.core.tokens import validate_token


logger = logging.getLogger(__name__)


@implementer(IPublishTraverse)
class OmniaProxyView(BrowserView):
    """Proxy JS API requests to the Omnia Core API service.

    Registered at @@omnia-api, this view captures sub-paths via IPublishTraverse
    (e.g. @@omnia-api/v1/agents/improve-text) and forwards them to the
    OmniaCoreAPIService, which adds authentication headers and dispatches to
    the upstream API.

    Access is enforced by the dedicated browser view permission declared in
    ZCML, while CSRF protection relies on the _authenticator token sent by the
    JS client.

    The proxy is disabled by default and must be enabled via the
    IOmniaCoreSettings.enable_proxy registry flag (set to True by
    imio.omnia.tinymce on install).
    """

    def __init__(self, context, request):
        super().__init__(context, request)
        self._path_segments = []

    def publishTraverse(self, request, name):
        self._path_segments.append(name)
        return self

    def __call__(self):
        self.request.response.setHeader("Content-Type", "application/json")

        enabled = get_enable_proxy()
        if not enabled:
            self.request.response.setStatus(404)
            return json.dumps({"error": "Not found"})

        path = "/" + "/".join(self._path_segments)

        try:
            body = json.loads(self.request.BODY)
        except (ValueError, TypeError):
            self.request.response.setStatus(400)
            return json.dumps({"error": "Invalid JSON body"})

        service = getMultiAdapter(
            (self.context, self.request), IOmniaCoreAPIService
        )

        try:
            result = service.post_json(path, payload=body)
        except httpx.HTTPStatusError as exc:
            self.request.response.setStatus(exc.response.status_code)
            return json.dumps({"error": str(exc)})
        except Exception:
            logger.exception("Omnia proxy error")
            self.request.response.setStatus(502)
            return json.dumps({"error": "Upstream API error"})

        return json.dumps(result)


@implementer(IUnboundStreamIterator)
class SSEStreamIterator:
    """Wrap an httpx streaming response as a Zope IUnboundStreamIterator.

    Zope's ``response.write()`` buffers everything in a BytesIO and only
    delivers the data to the WSGI server when the view returns.  By
    returning an ``IUnboundStreamIterator`` instead, the WSGIPublisher
    hands it directly to waitress, which iterates and sends each chunk
    to the browser immediately — giving us real SSE streaming.
    """

    def __init__(self, client, response):
        self._client = client
        self._response = response
        self._iter = response.iter_bytes()
        self._closed = False
        self._error_sent = False

    def __iter__(self):
        return self

    def __next__(self):
        if self._closed:
            raise StopIteration
        try:
            return next(self._iter)
        except StopIteration:
            self._close()
            raise
        except Exception as exc:
            self._close()
            if not self._error_sent:
                self._error_sent = True
                error_msg = json.dumps({"error": str(exc)})
                return f"data: {error_msg}\n\n".encode("utf-8")
            raise StopIteration

    def _close(self):
        if not self._closed:
            self._closed = True
            try:
                self._response.close()
            except Exception:
                pass
            try:
                self._client.close()
            except Exception:
                pass

    def __del__(self):
        self._close()


@implementer(IPublishTraverse)
class OmniaOpenAIProxyView(BrowserView):
    """Streaming proxy for the OpenAI-compatible API (chat completions).

    Registered at @@omnia-openai-api, captures sub-paths via
    IPublishTraverse (e.g. @@omnia-openai-api/v1/chat/completions)
    and forwards them to the upstream OpenAI-compatible gateway with
    server-side credentials.

    Supports SSE streaming responses required by the chat completions
    endpoint. Enabled via the IOmniaCoreSettings.enable_openai_proxy
    registry flag. Access is controlled by a dedicated browser view
    permission.
    """

    def __init__(self, context, request):
        super().__init__(context, request)
        self._path_segments = []

    def publishTraverse(self, request, name):
        self._path_segments.append(name)
        return self

    def _json_error(self, status, message):
        self.request.response.setStatus(status)
        self.request.response.setHeader("Content-Type", "application/json")
        return json.dumps({"error": message})

    def _is_proxy_enabled(self):
        return get_enable_openai_proxy()

    def _read_json_body(self):
        try:
            body = json.loads(self.request.BODY)
        except (ValueError, TypeError):
            return None, self._json_error(400, "Invalid JSON body")
        if not isinstance(body, dict):
            return None, self._json_error(400, "Invalid JSON body")
        return body, None

    def _prepare_request_body(self, body):
        return body, None

    def __call__(self):
        # Disable CSRF protection — the frontend sends Bearer auth via
        # fetch(), not a form submission with _authenticator.
        alsoProvides(self.request, IDisableCSRFProtection)

        # --- Origin check ---
        origin = self.request.getHeader("Origin")
        if origin:
            portal_url = api.portal.get().absolute_url()
            if urlparse(origin).netloc != urlparse(portal_url).netloc:
                return self._json_error(403, "Origin not allowed")

        # --- HMAC token check ---
        # Zope's PAS moves the Authorization header to request._auth before
        # views run, so getHeader('Authorization') returns None. Read _auth
        # directly (falls back to getHeader for non-Zope contexts).
        auth_header = getattr(self.request, "_auth", "") or self.request.getHeader("Authorization", "")
        if not auth_header or not auth_header.startswith("Bearer "):
            return self._json_error(401, "Missing authorization")

        token = auth_header[len("Bearer "):]
        portal_url = api.portal.get().absolute_url()
        if not validate_token(token, portal_url):
            return self._json_error(403, "Invalid or expired token")

        if not self._is_proxy_enabled():
            return self._json_error(404, "Not found")

        openai_url = get_openai_api_url()
        if not openai_url:
            return self._json_error(503, "OpenAI API URL not configured")

        body, error = self._read_json_body()
        if error is not None:
            return error
        body, error = self._prepare_request_body(body)
        if error is not None:
            return error

        path = "/" + "/".join(self._path_segments)
        url = f"{openai_url.rstrip('/')}{path}"
        is_streaming = body.get("stream", False)

        service = getMultiAdapter(
            (self.context, self.request), IOmniaOpenAIService
        )
        headers = service._headers()
        headers["Content-Type"] = "application/json"

        if is_streaming:
            return self._stream_response(url, headers, body)
        else:
            return self._json_response(url, headers, body)

    def _stream_response(self, url, headers, body):
        """Stream SSE response back to the browser via IUnboundStreamIterator."""
        response = self.request.response
        response.setHeader("Content-Type", "text/event-stream")
        response.setHeader("Cache-Control", "no-cache")
        response.setHeader("X-Accel-Buffering", "no")

        logger.debug("OpenAI proxy request body: %s", json.dumps(body))

        client = httpx.Client(timeout=120.0)
        try:
            req = client.build_request("POST", url, headers=headers, json=body)
            upstream = client.send(req, stream=True)
            upstream.raise_for_status()
            return SSEStreamIterator(client, upstream)
        except httpx.HTTPStatusError as exc:
            try:
                error_body = exc.response.read().decode("utf-8", errors="replace")
            except Exception:
                error_body = "(unreadable)"
            client.close()
            logger.warning(
                "OpenAI proxy upstream HTTP error: %s\nRequest body: %s\nResponse body: %s",
                exc,
                json.dumps(body),
                error_body,
            )
            response.setHeader("Content-Type", "application/json")
            response.setStatus(exc.response.status_code)
            return json.dumps({"error": str(exc)})
        except Exception:
            client.close()
            logger.exception("OpenAI proxy streaming error")
            response.setHeader("Content-Type", "application/json")
            response.setStatus(502)
            return json.dumps({"error": "Upstream API error"})

    def _json_response(self, url, headers, body):
        """Standard JSON proxy (non-streaming)."""
        self.request.response.setHeader("Content-Type", "application/json")
        try:
            resp = httpx.request(
                "POST", url, headers=headers, json=body, timeout=60.0
            )
            self.request.response.setStatus(resp.status_code)
            return resp.text
        except httpx.HTTPStatusError as exc:
            self.request.response.setStatus(exc.response.status_code)
            return json.dumps({"error": str(exc)})
        except Exception:
            logger.exception("OpenAI proxy error")
            self.request.response.setStatus(502)
            return json.dumps({"error": "Upstream API error"})
