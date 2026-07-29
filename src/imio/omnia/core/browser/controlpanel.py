# -*- coding: utf-8 -*-
from Products.CMFCore.ActionInformation import ActionInfo
from Products.CMFCore.Expression import getExprContext
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from imio.omnia.core import _
from plone import api
from plone.app.registry.browser.controlpanel import ControlPanelFormWrapper
from plone.app.registry.browser.controlpanel import RegistryEditForm
from plone.z3cform import layout
from zope import schema
from zope.interface import Interface
from zope.schema.vocabulary import SimpleTerm
from zope.schema.vocabulary import SimpleVocabulary

CORE_AUTH_TYPES = SimpleVocabulary(
    [
        SimpleTerm("none", "none", _("None (no authentication)")),
        SimpleTerm("oauth2", "oauth2", _("OAuth 2.0 (Keycloak SSO-Apps)")),
    ]
)

OPENAI_AUTH_TYPES = SimpleVocabulary(
    [
        SimpleTerm("none", "none", _("None (no authentication)")),
        SimpleTerm("api_key", "api_key", _("Static API key")),
        SimpleTerm("oauth2", "oauth2", _("OAuth 2.0 (Keycloak SSO-Apps)")),
    ]
)

GRANT_TYPES = SimpleVocabulary(
    [
        SimpleTerm("password", "password", _("Password Credentials (ROPC)")),
        SimpleTerm("client_credentials", "client_credentials", _("Client Credentials")),
    ]
)

CLIENT_AUTH_METHODS = SimpleVocabulary(
    [
        SimpleTerm("client_secret_basic", "client_secret_basic", _("Basic header (client_secret_basic)")),
        SimpleTerm("client_secret_post", "client_secret_post", _("Request body (client_secret_post)")),
    ]
)


class IOmniaCoreSettings(Interface):
    core_api_url = schema.TextLine(
        title=_("Omnia Core API URL"),
        required=False,
    )

    openai_api_url = schema.TextLine(
        title=_("OpenAI API URL"),
        required=False,
    )

    openai_extra_headers = schema.Dict(
        title=_("OpenAI extra headers"),
        description=_("Additional HTTP headers sent to the OpenAI-compatible API."),
        key_type=schema.TextLine(title=_("Header name")),
        value_type=schema.TextLine(title=_("Header value")),
        required=False,
        default={},
    )

    application_id = schema.TextLine(
        title=_("Application ID"),
        required=False,
    )

    organization_id = schema.TextLine(
        title=_("Organization ID"),
        required=False,
    )

    enable_proxy = schema.Bool(
        title=_("Enable Omnia API proxy"),
        description=_("Expose @@omnia-api endpoint. Access is controlled by permissions."),
        required=False,
        default=False,
    )

    enable_openai_proxy = schema.Bool(
        title=_("Enable OpenAI API proxy"),
        description=_("Expose @@omnia-openai-api endpoint. Access is controlled by permissions."),
        required=False,
        default=False,
    )

    api_timeout = schema.Int(
        title=_("API timeout (seconds)"),
        description=_("Timeout for HTTP requests to Omnia APIs, in seconds."),
        required=False,
        default=30,
    )

    core_auth_type = schema.Choice(
        title=_("Omnia Core API authentication"),
        description=_("How outbound requests to the Omnia Core API authenticate."),
        vocabulary=CORE_AUTH_TYPES,
        default="oauth2",
        required=True,
    )

    openai_auth_type = schema.Choice(
        title=_("OpenAI gateway authentication"),
        description=_(
            "How outbound requests to the OpenAI-compatible gateway authenticate. "
            '"Static API key" sends the OpenAI API Key below.'
        ),
        vocabulary=OPENAI_AUTH_TYPES,
        default="oauth2",
        required=True,
    )

    openai_api_key = schema.TextLine(
        title=_("OpenAI API Key"),
        description=_('Sent as a Bearer token when the OpenAI gateway authentication is "Static API key".'),
        required=False,
    )

    oauth_grant_type = schema.Choice(
        title=_("OAuth 2.0 grant type"),
        vocabulary=GRANT_TYPES,
        default="password",
        required=True,
    )

    oauth_client_id = schema.TextLine(
        title=_("OAuth 2.0 client ID"),
        required=False,
    )

    oauth_client_secret = schema.TextLine(
        title=_("OAuth 2.0 client secret"),
        required=False,
    )

    oauth_token_url = schema.TextLine(
        title=_("OAuth 2.0 token endpoint URL"),
        description=_("E.g. https://<keycloak>/realms/sso-apps/protocol/openid-connect/token."),
        required=False,
    )

    oauth_scope = schema.TextLine(
        title=_("OAuth 2.0 scope"),
        description=_("Optional, often empty for client_credentials."),
        required=False,
    )

    oauth_client_auth_method = schema.Choice(
        title=_("OAuth 2.0 client authentication method"),
        vocabulary=CLIENT_AUTH_METHODS,
        default="client_secret_basic",
        required=True,
    )

    oauth_username = schema.TextLine(
        title=_("OAuth 2.0 username (service account)"),
        description=_("Only used with the Password Credentials (ROPC) grant."),
        required=False,
    )

    oauth_password = schema.TextLine(
        title=_("OAuth 2.0 password (service account)"),
        description=_("Only used with the Password Credentials (ROPC) grant."),
        required=False,
    )


class OmniaCoreControlPanelForm(RegistryEditForm):
    label = _("Main Omnia settings")
    schema = IOmniaCoreSettings
    schema_prefix = "imio.omnia.IOmniaCoreSettings"


class OmniaCoreControlPanelFormWrapper(ControlPanelFormWrapper):

    index = ViewPageTemplateFile("controlpanel_layout.pt")

    def __init__(self, context, request):
        super().__init__(context, request)
        self.tabs = self.get_omnia_controlpanel_tabs()
        self.active_tab = self.get_active_tab()

    def get_omnia_controlpanel_tabs(self):
        portal_actions = api.portal.get_tool("portal_actions")
        actions = portal_actions.listActions(categories=["omnia_controlpanel_tabs"])
        ec = getExprContext(self)
        actions = [ActionInfo(action, ec) for action in actions]
        return actions

    def get_active_tab(self):
        return next(filter(lambda x: x["url"].split("/")[-1] == self.request.getURL().split("/")[-1], self.tabs))


OmniaCoreControlPanelView = layout.wrap_form(OmniaCoreControlPanelForm, OmniaCoreControlPanelFormWrapper)
