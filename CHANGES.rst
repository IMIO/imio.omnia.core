Changelog
=========


1.0a2 (unreleased)
------------------

- Updated package description to better reflect its role as shared infrastructure.
  [duchenean]


1.0a1 (2026-04-03)
------------------

- Initial release.
  [duchenean]
- Added ``OmniaCoreAPIService`` multi-adapter wrapping the Omnia Core API
  (``/imio/omnia/core/v1/agents/``): expand, improve, reduce, correct,
  translate, make accessible, suggest titles, convert meeting notes,
  categorize content, and extract metadata.
  [duchenean]
- Added ``OmniaOpenAIService`` multi-adapter wrapping the OpenAI-compatible
  Omnia gateway (``/imio/omnia/openai/v1/``): model listing and chat
  completions with streaming SSE support.
  [duchenean]
- Added shared Omnia control panel (``@@omnia-ai-settings``) with tabbed
  navigation extensible via ``omnia_controlpanel_tabs`` portal actions.
  [duchenean]
- Added "AI assistant" content menu with dynamic action collection via
  ``IOmniaActionsProvider`` utilities.
  [duchenean]
- Added ``IOrganizationIDProvider`` adapter interface for context-aware
  organization ID resolution.
  [duchenean]
- Added environment variable to registry sync on Zope startup
  (``OMNIA_CORE_API_URL``, ``OMNIA_OPENAI_API_URL``, ``OMNIA_APPLICATION_ID``,
  ``OMNIA_ORGANIZATION_ID``).
  [duchenean]
- Added HMAC-signed token generation for securing browser-to-proxy
  communication.
  [duchenean]
- Added ``IImioOmniaControlPanelFieldProvider`` interface for extending the
  control panel schema from downstream packages.
  [duchenean]
- Added Omnia SVG branding icons.
  [duchenean]
- Added i18n support (en, fr).
  [duchenean]
