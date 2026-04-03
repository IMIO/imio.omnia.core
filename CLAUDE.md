# imio.omnia.core

Plone 6 add-on providing the foundational infrastructure for "Omnia" — iMio's AI-assisted features in Plone. This package provides settings management, a shared control panel, action menus, extensibility interfaces, and branding assets. Other `imio.omnia.*` packages extend it.

## Project layout

```
src/imio/omnia/core/
├── browser/
│   ├── controlpanel.py          # @@omnia-ai-settings registry form + tabbed wrapper
│   ├── menu.py                  # "AI assistant" content menu + action providers
│   ├── controlpanel_layout.pt   # Tabbed control panel page template
│   ├── resources/               # Vite + React frontend (dev: npm run dev, build: npm run build)
│   ├── static/                  # Omnia SVG icons
│   ├── overrides/               # z3c.jbot template overrides
│   └── configure.zcml           # Browser layer, views, menu, adapter registrations
├── profiles/
│   ├── default/                 # GenericSetup install profile
│   │   ├── actions.xml          # omnia_controlpanel_tabs + omnia_actions categories
│   │   ├── controlpanel.xml     # @@omnia-ai-settings configlet
│   │   └── registry/main.xml   # Icon registry entries
│   └── uninstall/               # GenericSetup uninstall profile
├── locales/                     # i18n (en, fr)
├── tests/                       # test_setup.py — install/uninstall tests
├── interfaces.py                # IImioOmniaCoreLayer, IImioOmniaControlPanelFieldProvider, IOmniaActionsProvider, IOrganizationIDProvider
├── services.py                  # IOmniaCoreAPIService, IOmniaOpenAIService, OrganizationIDProvider
├── settings.py                  # Env var → registry sync on startup (IDatabaseOpenedWithRoot)
├── testing.py                   # IMIO_OMNIA_CORE_*_TESTING fixtures
├── setuphandlers.py             # HiddenProfiles, post_install, uninstall hooks
├── configure.zcml               # Root ZCML — profiles, permissions, browser include
└── permissions.zcml             # Permission definitions (currently empty)
```

## Development

This package is developed inside the parent `imio.omnia` buildout. From the buildout root (`../../..`):

```bash
bin/buildout                    # Install all develop eggs
bin/instance fg                 # Start Plone on port 8080 (admin:admin)
```

### Running tests

From this package directory:

```bash
tox -e py312-Plone61            # Run tests against Plone 6.1
tox -l                          # List all test environments
```

Or via the parent buildout:

```bash
../../bin/test -s imio.omnia.core
```

### Code quality

```bash
tox -e black-check              # Check formatting
tox -e black-enforce            # Apply formatting
tox -e py312-lint               # isort + flake8
tox -e isort-apply              # Fix import order
```

### Frontend assets

```bash
cd src/imio/omnia/core/browser/resources
npm install
npm run dev                     # Vite dev server
npm run build                   # Production build
```

## Code style

- Formatter: **Black** (line length 120)
- Import sorting: **isort** with `profile = plone`
- Linter: **flake8** (ignores: W503, C812, E501, T001, C813, C101)
- i18n domain: `imio.omnia.core` — use `from imio.omnia.core import _` for message strings

## Key extension points

- **IOrganizationIDProvider**: Adapter on `(context,)` that returns the organization ID string. Default reads from registry. Subpackages register more specific adapters (on narrower content type interfaces) to resolve the org ID from the content hierarchy.
- **IOmniaActionsProvider**: Register a utility implementing this interface to inject custom menu actions into the "AI assistant" content menu. Actions are collected via `getAllUtilitiesRegisteredFor(IOmniaActionsProvider)` in `menu.py`.
- **omnia_controlpanel_tabs**: Add portal_actions in this category to register new tabs in the shared Omnia control panel. Each tab links to a separate `@@view`.
- **omnia_actions**: Add portal_actions in this category to register actions in the "AI assistant" content menu.
- **IImioOmniaControlPanelFieldProvider**: Form field provider interface for extending the control panel schema.

## Registry settings

Stored under `imio.omnia.core.browser.controlpanel.IOmniaCoreSettings`:

- `core_api_url` — Omnia Core API URL
- `openai_api_url` — OpenAI API URL
- `application_id` — Application ID
- `organization_id` — Organization ID

## Services

Two HTTP client adapters wrapping the iMio Omnia APIs. Both are multi-adapters on `(context, request)`.

**OmniaCoreAPIService** (`IOmniaCoreAPIService`): wraps `/imio/omnia/core/v1/agents/` — text expansion, improvement, reduction, correction, translation, accessibility, title suggestion, meeting notes conversion, content categorization, metadata extraction. API spec: https://ipa.imio.be/imio/omnia/core/openapi.json

**OmniaOpenAIService** (`IOmniaOpenAIService`): wraps `/imio/omnia/openai/v1/` — OpenAI-compatible gateway with `list_models()` and `chat_completions()` (supports streaming). API spec: https://ipa.imio.be/imio/omnia/openai/openapi.json

Usage:
```python
from zope.component import getMultiAdapter
from imio.omnia.core.services import IOmniaCoreAPIService

service = getMultiAdapter((context, request), IOmniaCoreAPIService)
result = service.improve_text("Le projet va bien.")
```

Both services send `x-imio-application` (from registry) and `x-imio-municipality` (from `IOrganizationIDProvider` adapter) headers on every request.

## Environment variables

Set via buildout `environment-vars` or shell. Synced to registry on startup via `IDatabaseOpenedWithRoot` subscriber (requires `SITE_ID`).

| Env var | Registry field |
|---------|---------------|
| `SITE_ID` | Target Plone site ID in ZODB |
| `OMNIA_CORE_API_URL` | `core_api_url` |
| `OMNIA_OPENAI_API_URL` | `openai_api_url` |
| `OMNIA_APPLICATION_ID` | `application_id` |
| `OMNIA_ORGANIZATION_ID` | `organization_id` |

## Architecture notes

- Auto-included in Plone via `z3c.autoinclude.plugin` entry point (target: `plone`).
- Browser layer `IImioOmniaCoreLayer` gates all views and overrides — only active when the add-on is installed.
- Namespace packages: `imio`, `imio.omnia` — shared across sibling packages (`imio.omnia.tinymce`, etc.).
