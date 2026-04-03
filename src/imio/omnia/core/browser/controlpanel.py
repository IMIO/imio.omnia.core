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


class IOmniaCoreSettings(Interface):
    core_api_url = schema.TextLine(
        title=_("Omnia Core API URL"),
        required=False,
    )

    openai_api_url = schema.TextLine(
        title=_("OpenAI API URL"),
        required=False,
    )

    openai_api_key = schema.TextLine(
        title=_("OpenAI API Key"),
        description=_("Optional Bearer token sent to the OpenAI-compatible API."),
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
        description=_(
            "Expose @@omnia-api endpoint. Access is controlled by permissions."
        ),
        required=False,
        default=False,
    )

    enable_openai_proxy = schema.Bool(
        title=_("Enable OpenAI API proxy"),
        description=_(
            "Expose @@omnia-openai-api endpoint. Access is controlled by permissions."
        ),
        required=False,
        default=False,
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
        portal_actions = api.portal.get_tool('portal_actions')
        actions = portal_actions.listActions(categories=['omnia_controlpanel_tabs'])
        ec = getExprContext(self)
        actions = [ActionInfo(action, ec) for action in actions]
        return actions

    def get_active_tab(self):
        return next(filter(lambda x: x['url'].split('/')[-1] == self.request.getURL().split('/')[-1], self.tabs))


OmniaCoreControlPanelView = layout.wrap_form(OmniaCoreControlPanelForm, OmniaCoreControlPanelFormWrapper)
