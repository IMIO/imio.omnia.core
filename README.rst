===============
imio.omnia.core
===============

Shared infrastructure for the Omnia AI-assisted features suite in Plone 6.

This package provides settings management, a shared tabbed control panel, an
"AI assistant" content menu, HTTP client services wrapping the Omnia APIs,
extensibility interfaces, and branding assets. Other ``imio.omnia.*`` packages
(``imio.omnia.tinymce``, ``imio.omnia.classification``, etc.) build on top of
it.


Installation
============

Add the egg to your buildout::

    [buildout]

    ...

    eggs =
        imio.omnia.core

Then run ``bin/buildout``.

The package is auto-included in Plone via ``z3c.autoinclude.plugin``, so no
ZCML slug is needed.

Sub-packages that depend on ``imio.omnia.core`` should declare a GenericSetup
dependency in their ``profiles/default/metadata.xml``::

    <?xml version="1.0"?>
    <metadata>
      <version>1000</version>
      <dependencies>
        <dependency>profile-imio.omnia.core:default</dependency>
      </dependencies>
    </metadata>


Configuration
=============

Registry settings
-----------------

Stored under the prefix ``imio.omnia.IOmniaCoreSettings``:

======================  ====================================================================
Field                   Purpose
======================  ====================================================================
core_api_url            Omnia Core API base URL
openai_api_url          Omnia OpenAI-compatible gateway base URL
openai_api_key          Optional Bearer token sent to the OpenAI-compatible API
openai_extra_headers    Additional HTTP headers for the OpenAI-compatible API (dict)
application_id          Application identifier (sent as ``x-imio-application`` header)
organization_id         Default organization / municipality ID (``x-imio-municipality``)
enable_proxy            Enable ``@@omnia-api`` proxy endpoint (default: ``False``)
enable_openai_proxy     Enable ``@@omnia-openai-api`` streaming proxy (default: ``False``)
======================  ====================================================================

These settings are editable via the Omnia control panel at
``@@omnia-ai-settings`` (Site Setup > Omnia).

Environment variables
---------------------

Settings can also be driven by environment variables. They are synced to the
Plone registry on Zope startup (requires ``SITE_ID`` to locate the Plone
site):

=========================  ================
Variable                   Registry field
=========================  ================
``SITE_ID``                Plone site ID in the ZODB (not stored in registry)
``OMNIA_CORE_API_URL``     ``core_api_url``
``OMNIA_OPENAI_API_URL``   ``openai_api_url``
``OMNIA_OPENAI_API_KEY``   ``openai_api_key``
``OMNIA_APPLICATION_ID``   ``application_id``
``OMNIA_ORGANIZATION_ID``  ``organization_id``
=========================  ================

Set them in ``buildout.cfg`` under ``[instance] environment-vars`` or export
them in your shell before starting Plone.


Extending imio.omnia.core
=========================

Adding a control panel tab
--------------------------

Each Omnia sub-package can contribute a tab to the shared control panel. The
tabbed layout is rendered by ``OmniaCoreControlPanelFormWrapper``, which reads
tabs from ``portal_actions`` in the ``omnia_controlpanel_tabs`` category.

**Step 1** — Define a settings schema and form (``browser/controlpanel.py``)::

    from imio.omnia.core.browser.controlpanel import OmniaCoreControlPanelFormWrapper
    from plone.app.registry.browser.controlpanel import RegistryEditForm
    from plone.z3cform import layout
    from zope import schema
    from zope.interface import Interface

    from my.package import _


    class IMySettings(Interface):
        my_option = schema.TextLine(
            title=_("My option"),
            required=False,
        )


    class MyControlPanelForm(RegistryEditForm):
        label = _("My add-on settings")
        schema = IMySettings


    MyControlPanelView = layout.wrap_form(
        MyControlPanelForm, OmniaCoreControlPanelFormWrapper
    )

**Step 2** — Register the view (``browser/configure.zcml``)::

    <browser:page
      name="my-addon-settings"
      for="Products.CMFPlone.interfaces.IPloneSiteRoot"
      class=".controlpanel.MyControlPanelView"
      permission="cmf.ManagePortal"
      layer="my.package.interfaces.IMyBrowserLayer"
    />

**Step 3** — Register the tab (``profiles/default/actions.xml``)::

    <?xml version="1.0"?>
    <object name="portal_actions" meta_type="Plone Actions Tool"
            xmlns:i18n="http://xml.zope.org/namespaces/i18n">
      <object name="omnia_controlpanel_tabs" meta_type="CMF Action Category">
        <object name="my.package" meta_type="CMF Action">
          <property name="title" i18n:translate="">My add-on</property>
          <property name="url_expr">string:${portal_url}/@@my-addon-settings</property>
          <property name="icon_expr">string:gear</property>
        </object>
      </object>
    </object>

**Step 4** — Register the settings in the Plone registry
(``profiles/default/registry/main.xml``)::

    <?xml version="1.0"?>
    <registry>
      <records interface="my.package.browser.controlpanel.IMySettings"
               prefix="my.package.IMySettings" />
    </registry>


Adding menu actions (AI assistant menu)
---------------------------------------

The "AI assistant" icon in the Plone toolbar opens a submenu populated from
two sources:

1. Static **portal actions** in the ``omnia_actions`` category.
2. Dynamic **IOmniaActionsProvider** utilities.

Approach A — Static actions via ``actions.xml``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Register a ``CMF Action`` in the ``omnia_actions`` category
(``profiles/default/actions.xml``)::

    <?xml version="1.0"?>
    <object name="portal_actions" meta_type="Plone Actions Tool"
            xmlns:i18n="http://xml.zope.org/namespaces/i18n">
      <object name="omnia_actions" meta_type="CMF Action Category">
        <object name="my_action" meta_type="CMF Action" i18n:domain="my.package">
          <property name="title" i18n:translate="">My AI action</property>
          <property name="description" i18n:translate="">Run my custom AI action.</property>
          <property name="url_expr">string:$object_url/@@my-ai-action-view</property>
          <property name="icon_expr">string:cpu</property>
          <property name="available_expr">object/@@my-ai-action-view/available|nothing</property>
          <property name="visible">True</property>
        </object>
      </object>
    </object>

Approach B — Dynamic actions via ``IOmniaActionsProvider``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Implement a utility that returns actions based on runtime conditions::

    from imio.omnia.core.interfaces import IOmniaActionsProvider
    from plone.protect.utils import addTokenToUrl
    from zope.interface import implementer


    @implementer(IOmniaActionsProvider)
    class MyActionsProvider:

        def __call__(self, context, request):
            # Return an empty list to hide the actions, or a list of dicts.
            return [
                {
                    "title": "My dynamic action",
                    "description": "Does something smart.",
                    "action": addTokenToUrl(
                        f"{context.absolute_url()}/@@my-action-view", request
                    ),
                    "selected": False,
                    "icon": "cpu",
                    "extra": {
                        "id": "plone-contentmenu-actions-my-action",
                        "separator": None,
                        "class": "actionicon-object_buttons-my-action",
                        "modal": "",  # empty string to open in a modal
                    },
                    "submenu": None,
                },
            ]

Register the utility in ``configure.zcml``::

    <utility
      provides="imio.omnia.core.interfaces.IOmniaActionsProvider"
      factory=".action.MyActionsProvider"
      name="my-actions"
    />


Using the API services
----------------------

Two HTTP client services wrap the upstream Omnia APIs. Both are multi-adapters
on ``(context, request)`` and automatically send ``x-imio-application`` and
``x-imio-municipality`` headers resolved from the registry and the
``IOrganizationIDProvider`` adapter.

IOmniaCoreAPIService
~~~~~~~~~~~~~~~~~~~~

Wraps the Omnia Core AI agents API (``/imio/omnia/core/v1/agents/``).

Available methods:

- ``expand_text(input, expansion_target=50)``
- ``improve_text(input)``
- ``reduce_text(input, reduction_target=30)``
- ``correct_text(input)``
- ``make_accessible(input)``
- ``translate_text(input, target_language)``
- ``suggest_titles(input)``
- ``convert_meeting_notes_to_minutes(meeting_name, meeting_notes)``
- ``categorize_content(input, vocabulary, unique=False)``
- ``deduce_metadata(input=None, image_url=None, image_file=None)``
- ``send(method, path, **kwargs)`` / ``post_json(path, payload)`` for raw calls

Usage::

    from zope.component import getMultiAdapter
    from imio.omnia.core.interfaces import IOmniaCoreAPIService

    service = getMultiAdapter((context, request), IOmniaCoreAPIService)
    result = service.improve_text("Le projet va bien.")
    # result is a parsed JSON dict from the upstream API

IOmniaOpenAIService
~~~~~~~~~~~~~~~~~~~

Wraps the Omnia OpenAI-compatible gateway (``/imio/omnia/openai/v1/``).

Available methods:

- ``list_models()``
- ``chat_completions(model, messages, stream=False, temperature=None, max_tokens=None, tools=None, tool_choice=None)``

Usage::

    from zope.component import getMultiAdapter
    from imio.omnia.core.interfaces import IOmniaOpenAIService

    service = getMultiAdapter((context, request), IOmniaOpenAIService)
    result = service.chat_completions(
        model="Mistral Large",
        messages=[{"role": "user", "content": "Hello"}],
    )

Streaming::

    for chunk in service.chat_completions(
        model="Mistral Large",
        messages=[{"role": "user", "content": "Hello"}],
        stream=True,
    ):
        # Each chunk is a parsed JSON dict (SSE data frame)
        print(chunk)


Overriding organization ID resolution
--------------------------------------

The ``IOrganizationIDProvider`` adapter resolves which organization /
municipality ID is sent with every API request. The default implementation
reads from the registry (the ``organization_id`` setting).

To override the resolution for specific content types, register a more specific
adapter::

    from zope.component import adapter
    from zope.interface import implementer
    from imio.omnia.core.interfaces import IOrganizationIDProvider
    from my.package.interfaces import IMyContentType


    @adapter(IMyContentType)
    @implementer(IOrganizationIDProvider)
    class MyOrganizationIDProvider:

        def __init__(self, context):
            self.context = context

        def __call__(self):
            # Resolve the org ID from the content hierarchy
            return self.context.municipality_code

Register in ``configure.zcml``::

    <adapter factory=".adapters.MyOrganizationIDProvider" />

Zope's adapter specificity ensures your adapter is used for
``IMyContentType`` objects while the default adapter handles everything else.


Using the proxy view (@@omnia-api)
----------------------------------

The ``@@omnia-api`` view forwards browser JavaScript requests to the Omnia
Core API, adding authentication headers server-side. This avoids exposing API
credentials to the browser.

**Requirements:**

- The ``enable_proxy`` setting must be ``True`` (disabled by default).
- The caller must have the ``imio.omnia.core: Access Omnia API proxy``
  permission (granted to ``Authenticated`` by default).
- Requests must be POST with a JSON body.

**URL pattern:** ``<context_url>/@@omnia-api/<path>`` where ``<path>`` maps to
the upstream API path (e.g. ``/v1/agents/improve-text``).

**JavaScript example:**

.. code::

    const response = await fetch(
      `${portalUrl}/@@omnia-api/v1/agents/improve-text`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input: selectedText }),
      }
    );
    const data = await response.json();


Using the streaming proxy (``@@omnia-openai-api``)
--------------------------------------------------

The ``@@omnia-openai-api`` view proxies browser requests to the
OpenAI-compatible gateway and streams the response back as Server-Sent Events
(SSE). This lets browser-side chat widgets stream completions without exposing
API credentials or the upstream URL to the client.

**Requirements:**

- The ``enable_openai_proxy`` setting must be ``True`` (disabled by default).
- The caller must have the ``imio.omnia.core: Access Omnia OpenAI proxy``
  permission (granted to ``Authenticated`` by default).
- Requests must carry an HMAC Bearer token generated by
  ``imio.omnia.core.tokens.generate_token()``.

Projects that need anonymous access to ``@@omnia-openai-api`` can override the
default role mapping in their own GenericSetup ``rolemap.xml`` by granting the
``imio.omnia.core: Access Omnia OpenAI proxy`` permission to ``Anonymous``.

**Token generation (server-side, e.g. in a viewlet):**

.. code:: python

    from imio.omnia.core.tokens import generate_token

    token = generate_token(context.portal_url())
    # Pass this token to the browser as a JS variable

Tokens are HMAC-SHA256 signed using the Plone site keyring and expire after
2 hours. The proxy validates them on every request.

**URL pattern:** ``<context_url>/@@omnia-openai-api/<path>`` where ``<path>``
maps to the upstream API path (e.g. ``chat/completions``).

**JavaScript example:**

.. code::

    const response = await fetch(
      `${portalUrl}/@@omnia-openai-api/chat/completions`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`,
        },
        body: JSON.stringify({
          model: "Mistral Large",
          messages: [{ role: "user", content: "Hello" }],
          stream: true,
        }),
      }
    );

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      for (const line of decoder.decode(value).split("\n")) {
        if (!line.startsWith("data: ")) continue;
        const data = line.slice(6);
        if (data === "[DONE]") break;
        const chunk = JSON.parse(data);
        process.stdout.write(chunk.choices?.[0]?.delta?.content ?? "");
      }
    }


Available icons
===============

The following icon names are registered in the Plone icon registry and can be
used in ``icon_expr`` properties of portal actions:

==================================  =================
Icon name                           Description
==================================  =================
``omnia.ia.dark``                   Omnia IA (dark)
``omnia.ia.light``                  Omnia IA (light)
``omnia.monochrome.dark``           Monochrome (dark)
``omnia.monochrome.light``          Monochrome (light)
``omnia.picto.dark``                Pictogram (dark)
``omnia.picto.light``               Pictogram (light)
``omnia.logotype.dark``             Logotype (dark)
``omnia.logotype.light``            Logotype (light)
``omnia.imio.logotype.dark``        iMio logotype (dark)
``omnia.imio.logotype.light``       iMio logotype (light)
==================================  =================

The SVG files are served from ``++plone++imio.omnia.core/``.


Authors
=======

- `iMio, SCRL <https://imio.be>`_
- Antoine Duchene


License
=======

The project is licensed under the GPLv2.
