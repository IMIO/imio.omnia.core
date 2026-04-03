# -*- coding: utf-8 -*-
import hashlib
import hmac
import time

from plone.keyring.interfaces import IKeyManager
from zope.component import getUtility


def generate_token(portal_url):
    """Create an HMAC-signed token bound to the portal URL.

    Format: ``<timestamp>:<hmac_sha256_hex>``
    """
    manager = getUtility(IKeyManager)
    secret = manager.secret("_system")
    timestamp = str(int(time.time()))
    message = f"{portal_url}:{timestamp}"
    signature = hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{timestamp}:{signature}"


def validate_token(token, portal_url, max_age=7200):
    """Validate an HMAC-signed token.  Returns ``True`` if valid."""
    try:
        timestamp_str, signature = token.split(":", 1)
        timestamp = int(timestamp_str)
    except (ValueError, AttributeError):
        return False

    if time.time() - timestamp > max_age:
        return False

    manager = getUtility(IKeyManager)
    ring = manager[u"_system"]
    message = f"{portal_url}:{timestamp_str}"

    for secret in ring:
        if secret is None:
            continue
        expected = hmac.new(
            secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if hmac.compare_digest(signature, expected):
            return True

    return False
