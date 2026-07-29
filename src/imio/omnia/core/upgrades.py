# -*- coding: utf-8 -*-
"""GenericSetup upgrade steps."""
import logging

from plone.registry.interfaces import IRegistry
from zope.component import getUtility

from imio.omnia.core import REGISTRY_PREFIX

logger = logging.getLogger(__name__)


def upgrade_1000_to_1001(context):
    """create the core_auth_type / openai_auth_type / oauth_* registry records."""
    context.runImportStepFromProfile("profile-imio.omnia.core:default", "plone.app.registry")


def upgrade_1001_to_1002(context):
    """OAuth 2.0 becomes the default scheme for both services."""
    registry = getUtility(IRegistry)
    for field in ("core_auth_type", "openai_auth_type"):
        key = f"{REGISTRY_PREFIX}.{field}"
        if key in registry.records:
            registry[key] = "oauth2"
            logger.info("Set %s to oauth2", key)
    missing = [
        name
        for name in ("oauth_client_id", "oauth_client_secret", "oauth_token_url")
        if not registry.get(f"{REGISTRY_PREFIX}.{name}")
    ]
    if missing:
        logger.warning(
            "OAuth 2.0 is now the default authentication scheme but these settings "
            "are empty: %s. Configure them (control panel or SSO_APPS_* environment "
            "variables) or Omnia API calls will fail.",
            ", ".join(missing),
        )
