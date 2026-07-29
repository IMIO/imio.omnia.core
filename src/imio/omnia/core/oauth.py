# -*- coding: utf-8 -*-
"""OAuth 2.0 client machinery for the Omnia APIs.

This module is a port of authlib's synchronous httpx integration
(authlib/integrations/httpx_client/oauth2_client.py and utils.py,
authlib 1.7.2) with ``httpx`` replaced by ``httpx2``: authlib has no
httpx2 support and httpx is no longer part of this environment.
If a future authlib release supports httpx2, delete the port and
import ``OAuth2Client`` from authlib instead.

Re-verify this port against authlib's httpx_client sources whenever the
authlib pin moves, independent of httpx2 support.
"""

import logging
import threading
import typing

import httpx2
from authlib.integrations.base_client import InvalidTokenError
from authlib.integrations.base_client import MissingTokenError
from authlib.integrations.base_client import OAuthError
from authlib.integrations.base_client import UnsupportedTokenTypeError
from authlib.oauth2.auth import ClientAuth
from authlib.oauth2.auth import TokenAuth
from authlib.oauth2.client import OAuth2Client as _OAuth2Client
from httpx2 import USE_CLIENT_DEFAULT
from httpx2 import Auth
from httpx2 import Request
from httpx2 import Response
from imio.omnia.core.settings import get_api_timeout
from imio.omnia.core.settings import get_setting

logger = logging.getLogger(__name__)


HTTPX_CLIENT_KWARGS = [
    "headers",
    "cookies",
    "verify",
    "cert",
    "http1",
    "http2",
    "proxy",
    "mounts",
    "timeout",
    "follow_redirects",
    "limits",
    "max_redirects",
    "event_hooks",
    "base_url",
    "transport",
    "trust_env",
    "default_encoding",
]


def build_request(url, headers, body, initial_request: Request) -> Request:
    """Make sure that all the data from initial request is passed to the updated object."""
    updated_request = Request(method=initial_request.method, url=url, headers=headers, content=body)
    if hasattr(initial_request, "extensions"):
        updated_request.extensions = initial_request.extensions
    return updated_request


class OAuth2Auth(Auth, TokenAuth):
    """Sign requests for OAuth 2.0, currently only bearer token is supported."""

    requires_request_body = True

    def auth_flow(self, request: Request) -> typing.Generator[Request, Response, None]:
        try:
            url, headers, body = self.prepare(str(request.url), request.headers, request.content)
            headers["Content-Length"] = str(len(body))
            yield build_request(url=url, headers=headers, body=body, initial_request=request)
        except KeyError as error:
            description = f"Unsupported token_type: {str(error)}"
            raise UnsupportedTokenTypeError(description=description) from error


class OAuth2ClientAuth(Auth, ClientAuth):
    requires_request_body = True

    def auth_flow(self, request: Request) -> typing.Generator[Request, Response, None]:
        url, headers, body = self.prepare(request.method, str(request.url), request.headers, request.content)
        headers["Content-Length"] = str(len(body))
        yield build_request(url=url, headers=headers, body=body, initial_request=request)


class OAuth2Client(_OAuth2Client, httpx2.Client):
    SESSION_REQUEST_PARAMS = HTTPX_CLIENT_KWARGS

    client_auth_class = OAuth2ClientAuth
    token_auth_class = OAuth2Auth
    oauth_error_class = OAuthError

    def __init__(
        self,
        client_id=None,
        client_secret=None,
        token_endpoint_auth_method=None,
        revocation_endpoint_auth_method=None,
        scope=None,
        redirect_uri=None,
        token=None,
        token_placement="header",
        update_token=None,
        **kwargs,
    ):
        client_kwargs = self._extract_session_request_params(kwargs)
        app_value = client_kwargs.pop("app", None)
        if app_value is not None:
            client_kwargs["transport"] = httpx2.WSGITransport(app=app_value)

        httpx2.Client.__init__(self, **client_kwargs)

        _OAuth2Client.__init__(
            self,
            session=self,
            client_id=client_id,
            client_secret=client_secret,
            token_endpoint_auth_method=token_endpoint_auth_method,
            revocation_endpoint_auth_method=revocation_endpoint_auth_method,
            scope=scope,
            redirect_uri=redirect_uri,
            token=token,
            token_placement=token_placement,
            update_token=update_token,
            **kwargs,
        )

    @staticmethod
    def handle_error(error_type, error_description):
        raise OAuthError(error_type, error_description)

    def request(self, method, url, withhold_token=False, auth=USE_CLIENT_DEFAULT, **kwargs):
        if not withhold_token and auth is USE_CLIENT_DEFAULT:
            if not self.token:
                raise MissingTokenError()
            if not self.ensure_active_token(self.token):
                raise InvalidTokenError()
            auth = self.token_auth
        return super().request(method, url, auth=auth, **kwargs)

    def stream(self, method, url, withhold_token=False, auth=USE_CLIENT_DEFAULT, **kwargs):
        if not withhold_token and auth is USE_CLIENT_DEFAULT:
            if not self.token:
                raise MissingTokenError()
            if not self.ensure_active_token(self.token):
                raise InvalidTokenError()
            auth = self.token_auth
        return super().stream(method, url, auth=auth, **kwargs)


# --- process-level shared client -----------------------------------------

OAUTH_SETTINGS = (
    "oauth_grant_type",
    "oauth_client_id",
    "oauth_client_secret",
    "oauth_token_url",
    "oauth_scope",
    "oauth_client_auth_method",
    "oauth_username",
    "oauth_password",
)

_lock = threading.Lock()
_client = None
_fingerprint = None


def _read_config():
    cfg = {name: get_setting(name, default="") or "" for name in OAUTH_SETTINGS}
    cfg["api_timeout"] = get_api_timeout()
    return cfg


def _validate_config(cfg):
    required = ["oauth_client_id", "oauth_client_secret", "oauth_token_url"]
    if (cfg["oauth_grant_type"] or "password") == "password":
        required += ["oauth_username", "oauth_password"]
    missing = [name for name in required if not cfg[name]]
    if missing:
        raise ValueError("Incomplete OAuth2 configuration, missing: " + ", ".join(missing))


def _build_client(cfg):
    return OAuth2Client(
        client_id=cfg["oauth_client_id"],
        client_secret=cfg["oauth_client_secret"],
        token_endpoint_auth_method=cfg["oauth_client_auth_method"] or "client_secret_basic",
        scope=cfg["oauth_scope"] or None,
        token_endpoint=cfg["oauth_token_url"],
        grant_type=cfg["oauth_grant_type"] or "password",
        timeout=cfg["api_timeout"],
    )


def _fetch_token(client, cfg):
    grant_type = cfg["oauth_grant_type"] or "password"
    params = {}
    if grant_type == "password":
        params = {"username": cfg["oauth_username"], "password": cfg["oauth_password"]}
    client.fetch_token(cfg["oauth_token_url"], grant_type=grant_type, **params)


def _ensure_token(client, cfg):
    if not client.token:
        _fetch_token(client, cfg)
        return
    # Eager refresh window: refresh while the token still has more than
    # client.leeway (60s) + one request duration remaining, so
    # OAuth2Client.request()/stream() never enter their own, fallback-less
    # refresh path mid-request (that path would raise OAuthError to the
    # caller instead of re-fetching with the configured grant).
    leeway = client.leeway + cfg["api_timeout"]
    if client.token.is_expired(leeway=leeway):
        refresh_token = client.token.get("refresh_token")
        try:
            if refresh_token:
                client.refresh_token(cfg["oauth_token_url"], refresh_token=refresh_token)
            else:
                _fetch_token(client, cfg)
        except OAuthError:
            logger.info(
                "OAuth2 token refresh failed, re-fetching with %s grant",
                cfg["oauth_grant_type"],
            )
            _fetch_token(client, cfg)


def get_oauth_client():
    """Return the shared, token-carrying OAuth2 client for this process.

    Rebuilds the client when the registry configuration changes and
    guarantees the returned client holds a non-expired access token.
    Raises ValueError on incomplete configuration and authlib's
    OAuthError when the token endpoint rejects us.
    """
    global _client, _fingerprint
    cfg = _read_config()
    _validate_config(cfg)
    fingerprint = tuple(sorted(cfg.items()))
    # The lock intentionally serializes token refreshes across threads:
    # one refresh per expiry instead of a thundering herd against Keycloak.
    with _lock:
        if _client is None or fingerprint != _fingerprint:
            if _client is not None:
                try:
                    _client.close()
                except Exception:  # pragma: no cover
                    pass
            _client = _build_client(cfg)
            _fingerprint = fingerprint
        _ensure_token(_client, cfg)
        return _client


def reset_oauth_client():
    """Drop the shared client (tests, explicit invalidation)."""
    global _client, _fingerprint
    with _lock:
        if _client is not None:
            try:
                _client.close()
            except Exception:  # pragma: no cover
                pass
        _client = None
        _fingerprint = None
