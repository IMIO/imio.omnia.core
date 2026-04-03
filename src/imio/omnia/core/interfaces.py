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

    See: https://ipa.imio.be/imio/omnia/core/docs
    """

    def send(method, path, **kwargs):
        """Send a raw HTTP request to the upstream API and return parsed JSON."""

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


class IOmniaOpenAIService(Interface):
    """Client for the iMio Omnia OpenAI-compatible gateway.

    See: https://ipa.imio.be/imio/omnia/openai/docs
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
