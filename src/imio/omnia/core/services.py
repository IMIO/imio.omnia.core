import json
import logging
import time
from urllib.parse import urlparse
import httpx

from imio.helpers.security import fplog
from zope.component import adapter
from zope.component import getAdapter
from zope.interface import Interface
from zope.interface import implementer
from zope.publisher.interfaces.browser import IBrowserRequest

from imio.omnia.core.interfaces import IOrganizationIDProvider, IOmniaCoreAPIService, IOmniaOpenAIService
from imio.omnia.core.settings import get_application_id, get_openai_api_key, get_openai_extra_headers, get_setting

logger = logging.getLogger(__name__)


class BaseOmniaService:
    """Shared HTTP logic for Omnia service adapters."""

    registry_url_field = None  # override in subclasses

    def __init__(self, context, request):
        self.context = context
        self.request = request

    @property
    def base_url(self):
        return get_setting(self.registry_url_field, default="")

    def _headers(self):
        application_id = get_application_id()
        organization_id = getAdapter(self.context, IOrganizationIDProvider)()
        headers = {}
        if application_id:
            headers["x-imio-application"] = application_id
        if organization_id:
            headers["x-imio-municipality"] = organization_id
        return headers

    def _log_request(self, path, duration_ms, exc=None, extra=""):
        segment = path.rstrip("/").rsplit("/", 1)[-1] or path  # We'll keep just the action to keep the log shorter
        action = f"omnia.{segment}"
        details = f"duration_ms={duration_ms}"
        if extra:
            details += f" {extra}"
        fplog(action, details)
        if isinstance(exc, httpx.HTTPStatusError):
            logger.warning("Omnia API HTTP error: %s %s", action, details)
        elif exc is not None:
            logger.error("Omnia API unexpected error: %s %s", action, details, exc_info=exc)

    def send(self, method, path, **kwargs):
        url = f"{self.base_url}{path}"
        headers = {**self._headers(), **kwargs.pop("headers", {})}
        payload = kwargs.get("json") or kwargs.get("data")
        input_len = len(str(payload)) if payload else 0
        start = time.monotonic()
        error_extra = ""
        current_exc = None
        try:
            response = httpx.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            error_extra = f" error=http_{exc.response.status_code}"
            current_exc = exc
            raise
        except Exception as exc:
            error_extra = f" error={type(exc).__name__}"
            current_exc = exc
            raise
        finally:
            duration_ms = round((time.monotonic() - start) * 1000)
            self._log_request(path, duration_ms, exc=current_exc, extra=f"input_len={input_len}{error_extra}")

    def post_json(self, path, payload):
        return self.send("POST", path, json=payload)


@adapter(Interface, IBrowserRequest)
@implementer(IOmniaCoreAPIService)
class OmniaCoreAPIService(BaseOmniaService):
    registry_url_field = "core_api_url"

    def expand_text(self, input, expansion_target=50):
        return self.post_json(
            "/v1/agents/expand-text",
            {"input": input, "expansion_target": expansion_target},
        )

    def improve_text(self, input):
        return self.post_json("/v1/agents/improve-text", {"input": input})

    def reduce_text(self, input, reduction_target=30):
        return self.post_json(
            "/v1/agents/reduce-text",
            {"input": input, "reduction_target": reduction_target},
        )

    def suggest_titles(self, input):
        return self.post_json("/v1/agents/suggest-titles", {"input": input})

    def convert_meeting_notes_to_minutes(self, meeting_name, meeting_notes):
        return self.post_json(
            "/v1/agents/convert-meeting-notes-to-minutes",
            {"meeting_name": meeting_name, "meeting_notes": meeting_notes},
        )

    def categorize_content(self, input, vocabulary, unique=False):
        return self.post_json(
            "/v1/agents/categorize-content",
            {"input": input, "vocabulary": vocabulary, "unique": unique},
        )

    def correct_text(self, input):
        return self.post_json("/v1/agents/correct-text", {"input": input})

    def make_accessible(self, input):
        return self.post_json("/v1/agents/make-accessible", {"input": input})

    def translate_text(self, input, target_language):
        return self.post_json(
            "/v1/agents/translate-text",
            {"input": input, "target_language": target_language},
        )

    def deduce_metadata(self, input=None, image_url=None, image_file=None):
        data = {}
        files = {}
        if input is not None:
            data["input"] = input
        if image_url is not None:
            data["image_url"] = image_url
        if image_file is not None:
            files["image_file"] = image_file
        return self.send(
            "POST",
            "/v1/agents/deduce-metadata",
            data=data,
            files=files or None,
        )


@adapter(Interface, IBrowserRequest)
@implementer(IOmniaOpenAIService)
class OmniaOpenAIService(BaseOmniaService):
    registry_url_field = "openai_api_url"

    def _headers(self):
        # Only send iMio-specific headers (x-imio-application, x-imio-municipality)
        # to iMio-hosted endpoints; external providers (e.g. openai.com) reject them.
        if "imio.be" in urlparse(self.base_url).netloc:
            headers = super()._headers()
        else:
            headers = {}
        api_key = get_openai_api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        extra = get_openai_extra_headers()
        if extra:
            headers.update(extra)
        return headers

    def list_models(self):
        return self.send("GET", "/models")

    def chat_completions(
        self,
        model,
        messages,
        stream=False,
        temperature=None,
        max_tokens=None,
        tools=None,
        tool_choice=None,
    ):
        payload = {"model": model, "messages": messages, "stream": stream}
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if tools is not None:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice

        if not stream:
            return self.post_json("/chat/completions", payload)

        return self._stream_completions("/chat/completions", payload)

    def _stream_completions(self, path, payload):
        url = f"{self.base_url}{path}"
        headers = {**self._headers(), "Content-Type": "application/json"}
        input_len = len(str(payload))
        start = time.monotonic()
        error_extra = ""
        current_exc = None
        try:
            with httpx.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                yield from self._iter_sse(response)
        except httpx.HTTPStatusError as exc:
            error_extra = f" error=http_{exc.response.status_code}"
            current_exc = exc
            raise
        except Exception as exc:
            error_extra = f" error={type(exc).__name__}"
            current_exc = exc
            raise
        finally:
            duration_ms = round((time.monotonic() - start) * 1000)
            self._log_request(path, duration_ms, exc=current_exc, extra=f"input_len={input_len} streaming=true{error_extra}")

    @staticmethod
    def _iter_sse(response):
        """Yield parsed SSE data chunks from a streaming response."""
        for line in response.iter_lines():
            if not line or not line.startswith("data: "):
                continue
            data = line[len("data: "):]
            if data == "[DONE]":
                return
            yield json.loads(data)
