# -*- coding: utf-8 -*-
"""GenericSetup upgrade steps."""


def upgrade_1000_to_1001(context):
    """OIA-241: create the auth_type / oauth_* registry records."""
    context.runImportStepFromProfile("profile-imio.omnia.core:default", "plone.app.registry")
