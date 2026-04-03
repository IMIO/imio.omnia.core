import logging
import os

import transaction
from plone import api
from zope.component.hooks import setSite

from imio.omnia.core import REGISTRY_PREFIX

logger = logging.getLogger(__name__)

ENV_MAPPING = {
    "core_api_url": "OMNIA_CORE_API_URL",
    "openai_api_url": "OMNIA_OPENAI_API_URL",
    "openai_api_key": "OMNIA_OPENAI_API_KEY",
    "application_id": "OMNIA_APPLICATION_ID",
    "organization_id": "OMNIA_ORGANIZATION_ID",
}

def get_setting(field, default=None):
    """Return the value of an IOmniaCoreSettings registry field."""
    return api.portal.get_registry_record(
        f"{REGISTRY_PREFIX}.{field}", default=default
    )


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


def sync_env_to_registry(event):
    """On database open, write environment variable values into the Plone registry."""
    site_id = os.environ.get("SITE_ID")
    if not site_id:
        return

    env_values = {
        name: os.environ[env_var]
        for name, env_var in ENV_MAPPING.items()
        if os.environ.get(env_var)
    }
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
        for name, value in env_values.items():
            key = f"{REGISTRY_PREFIX}.{name}"
            if key in registry and registry[key] != value:
                registry[key] = value
                logger.info("Set %s from env var %s", key, ENV_MAPPING[name])
                changed = True

        if changed:
            transaction.commit()
    except Exception:
        transaction.abort()
        logger.exception("Failed to sync environment variables to registry")
    finally:
        setSite(None)
        conn.close()
