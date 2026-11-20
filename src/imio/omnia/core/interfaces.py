# -*- coding: utf-8 -*-
"""Module where all interfaces, events and exceptions live."""
from plone.autoform.interfaces import IFormFieldProvider
from zope.interface import Interface
from zope.publisher.interfaces.browser import IDefaultBrowserLayer


class IImioOmniaCoreLayer(IDefaultBrowserLayer):
    """Marker interface that defines a browser layer."""

class IImioOmniaControlPanelFieldProvider(IFormFieldProvider):
    pass


class IOmniaActionsProvider(Interface):
    def __call__(self, context, request):
        pass


class IOrganizationIDProvider(Interface):
    """Adapter that resolves the organization ID for a given context.

    Register more specific adapters in subpackages to override
    the default (which reads from the Plone registry).
    """

    def __call__():
        """Return the organization ID as a string."""


class IOmniaCoreAPIService(Interface):
    """Client for the iMio Omnia Core AI agents API.

    See the ``/imio/omnia/core/docs`` OpenAPI page on the iMio API gateway.
    """

    def send(method, path, timeout=None, **kwargs):
        """Send a raw HTTP request to the upstream API and return parsed JSON.

        ``timeout`` is in seconds. The default is the ``api_timeout`` registry setting.
        """

    def post_json(path, **kwargs):
        """Send a raw POST HTTP request to the upstream API and return parsed JSON."""

    def expand_text(input, expansion_target=50):
        """Expand text by a target percentage."""

    def improve_text(input):
        """Improve clarity, coherence, and style."""

    def reduce_text(input, reduction_target=30):
        """Reduce text by a target percentage."""

    def suggest_titles(input):
        """Suggest titles for text."""

    def convert_meeting_notes_to_minutes(meeting_name, meeting_notes):
        """Convert meeting notes to structured minutes."""

    def categorize_content(input, vocabulary, unique=False):
        """Categorize text against a vocabulary."""

    def correct_text(input):
        """Correct spelling and grammar."""

    def make_accessible(input):
        """Make text WCAG-accessible."""

    def translate_text(input, target_language):
        """Translate text to a target language."""

    def deduce_metadata(input=None, image_url=None, image_file=None):
        """Extract title, description and keywords from text/image."""

    def ocr_markdown(
        file=None,
        document_url=None,
        pages=None,
        extract_header_footer=False,
        table_format=None,
        image_descriptions=False,
        confidence=False,
        timeout=None,
    ):
        """Convert a document to Markdown with OCR.

        Give exactly one of ``file`` and ``document_url``.
        ``file`` is a ``(filename, content, content_type)`` tuple.
        ``content`` is bytes or a binary file object.
        ``document_url`` is a public https URL.
        ``pages`` is a zero-based range string, for example ``"0-4,7"``.
        ``table_format`` is ``"markdown"`` or ``"html"``.
        ``timeout`` is in seconds. The default is 330 seconds.
        The API does not get an option that keeps its default value.

        Return a dict with the keys ``markdown``, ``pages``, ``page_count`` and ``model``.
        Raise ``ValueError`` if the call does not give exactly one document source.
        """

    def ocr_extractions(
        output_schema,
        file=None,
        document_url=None,
        strict=True,
        instructions=None,
        pages=None,
        extract_header_footer=False,
        table_format=None,
        image_descriptions=False,
        confidence=False,
        timeout=None,
    ):
        """Extract structured data from a document with OCR.

        ``output_schema`` is a JSON Schema of type object.
        It is a dict or a JSON string.
        ``strict`` makes the result obey the schema exactly.
        ``instructions`` is an optional text of 2000 characters maximum.
        The other parameters are the same as for ``ocr_markdown``.

        Return the ``ocr_markdown`` dict with one more key, ``data``.
        ``data`` holds the extracted object.
        Raise ``ValueError`` if the call does not give exactly one document source.
        """


class IOmniaOpenAIService(Interface):
    """Client for the iMio Omnia OpenAI-compatible gateway.

    The gateway base URL is configured by the ``openai_api_url`` registry setting.
    """

    def list_models():
        """List available models."""

    def chat_completions(
        model,
        messages,
        stream=False,
        temperature=None,
        max_tokens=None,
        tools=None,
        tool_choice=None,
    ):
        """Create a chat completion."""
