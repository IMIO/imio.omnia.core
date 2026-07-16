# -*- coding: utf-8 -*-
"""OAuth 2.0 client machinery for the Omnia APIs (OIA-241).

This module is a port of authlib's synchronous httpx integration
(authlib/integrations/httpx_client/oauth2_client.py and utils.py,
authlib 1.7.2) with ``httpx`` replaced by ``httpx2``: authlib has no
httpx2 support and DELIBE-322 removes httpx from the environment.
If a future authlib release supports httpx2, delete the port and
import ``OAuth2Client`` from authlib instead.
"""

import logging
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
