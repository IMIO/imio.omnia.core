import logging
import os
from contextlib import contextmanager
from io import BytesIO

import transaction
from plone import api
from zope.component.hooks import setSite
from zope.globalrequest import setRequest
from ZPublisher.HTTPRequest import HTTPRequest
from ZPublisher.HTTPResponse import HTTPResponse

from imio.omnia.core import REGISTRY_PREFIX

try:
    from collective.fingerpointing.interfaces import IFingerPointingSettings

    AUDIT_REGISTRY_RECORD = f"{IFingerPointingSettings.__identifier__}.audit_registry"
except ImportError:  # collective.fingerpointing is optional
    AUDIT_REGISTRY_RECORD = None

logger = logging.getLogger(__name__)

# Only free-text deployment inputs are configurable through the environment.
# The vocabulary-backed fields keep their schema defaults (oauth2 authentication,
# password grant, client_secret_basic) so a typo in a deployment environment can
# never persist a value the control panel would reject.
ENV_MAPPING = {
    "core_api_url": "OMNIA_CORE_API_URL",
    "openai_api_url": "OMNIA_OPENAI_API_URL",
    "openai_api_key": "OMNIA_OPENAI_API_KEY",
    "application_id": "OMNIA_APPLICATION_ID",
    "organization_id": "OMNIA_ORGANIZATION_ID",
    "oauth_client_id": "SSO_APPS_CLIENT_ID",
    "oauth_client_secret": "SSO_APPS_CLIENT_SECRET",
    "oauth_token_url": "SSO_APPS_URL",
    "oauth_username": "SSO_APPS_USER_USERNAME",
    "oauth_password": "SSO_APPS_USER_PASSWORD",
}


def get_setting(field, default=None):
    """Return the value of an IOmniaCoreSettings registry field."""
    return api.portal.get_registry_record(f"{REGISTRY_PREFIX}.{field}", default=default)


def set_setting(field, value):
    """Write a value to an IOmniaCoreSettings registry field."""
    api.portal.set_registry_record(f"{REGISTRY_PREFIX}.{field}", value)


def get_core_api_url():
    return get_setting("core_api_url", default="")


def set_core_api_url(value):
    set_setting("core_api_url", value)


def get_openai_api_url():
    return get_setting("openai_api_url", default="")


def set_openai_api_url(value):
    set_setting("openai_api_url", value)


def get_application_id():
    return get_setting("application_id", default="")


def set_application_id(value):
    set_setting("application_id", value)


def get_organization_id():
    return get_setting("organization_id", default="")


def set_organization_id(value):
    set_setting("organization_id", value)


def get_openai_api_key():
    return get_setting("openai_api_key", default="")


def set_openai_api_key(value):
    set_setting("openai_api_key", value)


def get_openai_extra_headers():
    return get_setting("openai_extra_headers", default={})


def get_enable_proxy():
    return get_setting("enable_proxy", default=False)


def set_enable_proxy(value):
    set_setting("enable_proxy", value)


def get_enable_openai_proxy():
    return get_setting("enable_openai_proxy", default=False)


def set_enable_openai_proxy(value):
    set_setting("enable_openai_proxy", value)


def get_api_timeout():
    return get_setting("api_timeout", default=30)


def get_core_auth_type():
    return get_setting("core_auth_type", default="oauth2")


def set_core_auth_type(value):
    set_setting("core_auth_type", value)


def get_openai_auth_type():
    return get_setting("openai_auth_type", default="oauth2")


def set_openai_auth_type(value):
    set_setting("openai_auth_type", value)


@contextmanager
def _startup_request():
    """Bind a minimal request to the current thread.

    There is no request while the database is being opened, but subscribers to
    registry changes assume there is one.
    """
    environ = {"SERVER_NAME": "localhost", "SERVER_PORT": "80", "REQUEST_METHOD": "GET"}
    request = HTTPRequest(BytesIO(b""), environ, HTTPResponse(stdout=BytesIO()))
    setRequest(request)
    try:
        yield
    finally:
        setRequest(None)


@contextmanager
def _audit_logging_disabled(registry):
    """Turn collective.fingerpointing off, when it is installed.

    It logs the new value of every record it sees change, and some of the
    records written here hold credentials.
    """
    enabled = AUDIT_REGISTRY_RECORD is not None and registry.get(AUDIT_REGISTRY_RECORD)
    if enabled:
        registry[AUDIT_REGISTRY_RECORD] = False
    try:
        yield
    finally:
        if enabled:
            registry[AUDIT_REGISTRY_RECORD] = True


def sync_env_to_registry(event):
    """On database open, write environment variable values into the Plone registry."""
    site_id = os.environ.get("SITE_ID")
    if not site_id:
        return

    env_values = {name: os.environ[env_var] for name, env_var in ENV_MAPPING.items() if os.environ.get(env_var)}
    if not env_values:
        return

    db = event.database
    conn = db.open()
    try:
        root = conn.root()
        app = root.get("Application")
        if app is None:
            return

        site = app.get(site_id)
        if site is None:
            logger.warning("SITE_ID=%s not found in ZODB", site_id)
            return

        setSite(site)
        registry = site.portal_registry
        changed = False
        with _startup_request(), _audit_logging_disabled(registry):
            for name, value in env_values.items():
                key = f"{REGISTRY_PREFIX}.{name}"
                if key in registry and registry[key] != value:
                    registry[key] = value
                    logger.info("Set %s from env var %s", key, ENV_MAPPING[name])
                    changed = True

        if changed:
            transaction.commit()
        else:
            # _audit_logging_disabled writes to the registry even when no value
            # changed, which joins the connection to a transaction. Closing a
            # joined connection raises ConnectionStateError, which would escape
            # this subscriber and abort Zope startup.
            transaction.abort()
    except Exception:
        transaction.abort()
        logger.exception("Failed to sync environment variables to registry")
    finally:
        setSite(None)
        try:
            conn.close()
        except Exception:
            # Syncing settings is a convenience; it must never prevent startup.
            logger.exception("Failed to close the registry sync connection")
