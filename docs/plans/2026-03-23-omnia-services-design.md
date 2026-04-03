# Omnia Services Implementation Design

## Context

`imio.omnia.core.services` needs to implement two HTTP client services that wrap the iMio Omnia APIs:

- **Core API** (`/imio/omnia/core/v1/agents/`) — 10 AI agent endpoints (text expansion, improvement, correction, translation, etc.)
- **OpenAI Gateway** (`/imio/omnia/openai/v1/`) — OpenAI-compatible API (models listing, chat completions with streaming and tool use)

The Organization ID must be customizable per-context via a Zope adapter so subpackages can override it.

## API References

- Core API: https://ipa.imio.be/imio/omnia/core/openapi.json
- OpenAI Gateway: https://ipa.imio.be/imio/omnia/openai/openapi.json

## Design

### Organization ID Adapter

`IOrganizationIDProvider` — adapter on `(context,)` returning a string.

- **Default** (registered in `imio.omnia.core`): reads `organization_id` from the Plone registry.
- **Override**: subpackages register more specific adapters on narrower interfaces (e.g., a specific content type) to resolve the org ID from the content hierarchy, a field, etc.

### Service Adapters

Both services are multi-adapters on `(context, request)`.

#### OmniaCoreAPIService

Base URL from registry: `core_api_url`.

All agent endpoints receive `x-imio-application` and `x-imio-municipality` headers.

Methods (all return parsed JSON response dict):

| Method | Endpoint | Request body |
|--------|----------|-------------|
| `expand_text(input, expansion_target=50)` | POST `/v1/agents/expand-text` | `TextExpandRequest` |
| `improve_text(input)` | POST `/v1/agents/improve-text` | `TextImproveRequest` |
| `reduce_text(input, reduction_target=30)` | POST `/v1/agents/reduce-text` | `TextShorterRequest` |
| `suggest_titles(input)` | POST `/v1/agents/suggest-titles` | `SuggestTitlesRequest` |
| `convert_meeting_notes_to_minutes(meeting_name, meeting_notes)` | POST `/v1/agents/convert-meeting-notes-to-minutes` | `MeetingRequest` |
| `categorize_content(input, vocabulary, unique=False)` | POST `/v1/agents/categorize-content` | `CategorizeContentRequest` |
| `correct_text(input)` | POST `/v1/agents/correct-text` | `TextCorrectRequest` |
| `make_accessible(input)` | POST `/v1/agents/make-accessible` | `TextAccessibleRequest` |
| `translate_text(input, target_language)` | POST `/v1/agents/translate-text` | `TextTranslateRequest` |
| `deduce_metadata(input=None, image_url=None, image_file=None)` | POST `/v1/agents/deduce-metadata` | multipart/form-data |

#### OmniaOpenAIService

Base URL from registry: `openai_api_url`.

Methods:

| Method | Endpoint |
|--------|----------|
| `list_models()` | GET `/v1/models` |
| `chat_completions(model, messages, stream=False, temperature=None, max_tokens=None, tools=None, tool_choice=None)` | POST `/v1/chat/completions` |

`chat_completions` returns a dict for non-streaming, or a generator for streaming responses.

### HTTP Layer

Shared base class providing a `_request(method, url, **kwargs)` helper that:

1. Reads base URL from registry (`core_api_url` or `openai_api_url`)
2. Resolves organization ID via `IOrganizationIDProvider(context)`
3. Reads application ID from registry
4. Sets `x-imio-application` and `x-imio-municipality` headers
5. Makes the HTTP call via `requests`
6. Raises `requests.HTTPError` on failure

### Files Changed

- `interfaces.py` — add `IOrganizationIDProvider`
- `services.py` — rewrite: `IOrganizationIDProvider`, `IOmniaCoreAPIService`, `IOmniaOpenAIService` interfaces; `OrganizationIDProvider`, `OmniaCoreAPIService`, `OmniaOpenAIService` implementations
- `configure.zcml` — register the three adapters
- `setup.py` — add `requests` to `install_requires`

## Implementation Plan

1. Add `IOrganizationIDProvider` to `interfaces.py`
2. Rewrite `services.py` with interfaces, base class, both service implementations, and default `OrganizationIDProvider`
3. Register adapters in `configure.zcml`
4. Add `requests` to `setup.py` dependencies
5. Update `CLAUDE.md`
