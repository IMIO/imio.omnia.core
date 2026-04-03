# -*- coding: utf-8 -*-
import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

import httpx
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID

from imio.omnia.core.services import OmniaCoreAPIService
from imio.omnia.core.services import OmniaOpenAIService
from imio.omnia.core.settings import set_application_id
from imio.omnia.core.settings import set_openai_api_key
from imio.omnia.core.settings import set_organization_id
from imio.omnia.core.settings import set_setting
from imio.omnia.core.testing import IMIO_OMNIA_CORE_INTEGRATION_TESTING


class TestServiceHeadersAndTransport(unittest.TestCase):
    layer = IMIO_OMNIA_CORE_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.request = self.layer["request"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        set_application_id("")
        set_organization_id("")
        set_openai_api_key("")
        set_setting("core_api_url", "")
        set_setting("openai_api_url", "")
        set_setting("openai_extra_headers", {})

    def test_core_headers_include_application_and_organization(self):
        set_application_id("omnia-app")
        set_organization_id("namur")

        service = OmniaCoreAPIService(self.portal, self.request)

        self.assertEqual(
            service._headers(),
            {
                "x-imio-application": "omnia-app",
                "x-imio-municipality": "namur",
            },
        )

    def test_core_headers_omit_empty_values(self):
        service = OmniaCoreAPIService(self.portal, self.request)

        self.assertEqual(service._headers(), {})

    def test_openai_headers_keep_imio_headers_for_imio_host(self):
        set_setting("openai_api_url", "https://ipa.imio.be/imio/omnia/openai/v1")
        set_application_id("omnia-app")
        set_organization_id("namur")
        set_openai_api_key("secret-token")
        set_setting("openai_extra_headers", {"X-Test": "extra"})

        service = OmniaOpenAIService(self.portal, self.request)

        self.assertEqual(
            service._headers(),
            {
                "x-imio-application": "omnia-app",
                "x-imio-municipality": "namur",
                "Authorization": "Bearer secret-token",
                "X-Test": "extra",
            },
        )

    def test_openai_headers_drop_imio_headers_for_external_host(self):
        set_setting("openai_api_url", "https://api.openai.example/v1")
        set_application_id("omnia-app")
        set_organization_id("namur")
        set_openai_api_key("secret-token")
        set_setting("openai_extra_headers", {"X-Test": "extra"})

        service = OmniaOpenAIService(self.portal, self.request)

        self.assertEqual(
            service._headers(),
            {
                "Authorization": "Bearer secret-token",
                "X-Test": "extra",
            },
        )

    @patch("imio.omnia.core.services.fplog")
    @patch("imio.omnia.core.services.httpx.request")
    def test_send_builds_request_and_logs_success(self, mock_request, mock_fplog):
        set_setting("core_api_url", "https://api.example.com")
        set_application_id("omnia-app")
        set_organization_id("namur")
        response = MagicMock()
        response.json.return_value = {"ok": True}
        response.raise_for_status.return_value = None
        mock_request.return_value = response
        payload = {"input": "bonjour"}

        service = OmniaCoreAPIService(self.portal, self.request)
        result = service.send("POST", "/v1/agents/improve-text", json=payload)

        self.assertEqual(result, {"ok": True})
        mock_request.assert_called_once_with(
            "POST",
            "https://api.example.com/v1/agents/improve-text",
            headers={
                "x-imio-application": "omnia-app",
                "x-imio-municipality": "namur",
            },
            json=payload,
        )
        action, details = mock_fplog.call_args[0]
        self.assertEqual(action, "omnia.improve-text")
        self.assertIn("input_len={}".format(len(str(payload))), details)
        self.assertIn("duration_ms=", details)

    @patch("imio.omnia.core.services.logger.warning")
    @patch("imio.omnia.core.services.fplog")
    @patch("imio.omnia.core.services.httpx.request")
    def test_send_logs_http_status_errors(
        self,
        mock_request,
        mock_fplog,
        mock_warning,
    ):
        set_setting("core_api_url", "https://api.example.com")
        response = MagicMock()
        response.status_code = 422
        error = httpx.HTTPStatusError(
            "bad request",
            request=MagicMock(),
            response=response,
        )
        mock_request.side_effect = error

        service = OmniaCoreAPIService(self.portal, self.request)

        with self.assertRaises(httpx.HTTPStatusError):
            service.send("POST", "/v1/agents/improve-text", json={"input": "bad"})

        action, details = mock_fplog.call_args[0]
        self.assertEqual(action, "omnia.improve-text")
        self.assertIn("error=http_422", details)
        mock_warning.assert_called_once()

    @patch("imio.omnia.core.services.logger.error")
    @patch("imio.omnia.core.services.fplog")
    @patch("imio.omnia.core.services.httpx.request")
    def test_send_logs_unexpected_errors(
        self,
        mock_request,
        mock_fplog,
        mock_error,
    ):
        set_setting("core_api_url", "https://api.example.com")
        mock_request.side_effect = RuntimeError("boom")

        service = OmniaCoreAPIService(self.portal, self.request)

        with self.assertRaises(RuntimeError):
            service.send("POST", "/v1/agents/improve-text", json={"input": "bad"})

        action, details = mock_fplog.call_args[0]
        self.assertEqual(action, "omnia.improve-text")
        self.assertIn("error=RuntimeError", details)
        mock_error.assert_called_once()

    def test_post_json_delegates_to_send(self):
        service = OmniaCoreAPIService(self.portal, self.request)

        with patch.object(service, "send", return_value={"ok": True}) as mock_send:
            result = service.post_json("/v1/agents/improve-text", {"input": "x"})

        self.assertEqual(result, {"ok": True})
        mock_send.assert_called_once_with(
            "POST",
            "/v1/agents/improve-text",
            json={"input": "x"},
        )


class TestOpenAIServiceMethods(unittest.TestCase):
    layer = IMIO_OMNIA_CORE_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.request = self.layer["request"]

    def test_chat_completions_non_streaming_omits_optional_fields(self):
        service = OmniaOpenAIService(self.portal, self.request)

        with patch.object(service, "post_json", return_value={"id": "1"}) as mock_post:
            result = service.chat_completions(
                model="gpt-test",
                messages=[{"role": "user", "content": "Hi"}],
            )

        self.assertEqual(result, {"id": "1"})
        mock_post.assert_called_once_with(
            "/chat/completions",
            {
                "model": "gpt-test",
                "messages": [{"role": "user", "content": "Hi"}],
                "stream": False,
            },
        )

    def test_chat_completions_streaming_includes_optional_fields(self):
        service = OmniaOpenAIService(self.portal, self.request)
        sentinel = object()

        with patch.object(
            service,
            "_stream_completions",
            return_value=sentinel,
        ) as mock_stream:
            result = service.chat_completions(
                model="gpt-test",
                messages=[{"role": "user", "content": "Hi"}],
                stream=True,
                temperature=0.2,
                max_tokens=512,
                tools=[{"type": "function"}],
                tool_choice="auto",
            )

        self.assertIs(result, sentinel)
        mock_stream.assert_called_once_with(
            "/chat/completions",
            {
                "model": "gpt-test",
                "messages": [{"role": "user", "content": "Hi"}],
                "stream": True,
                "temperature": 0.2,
                "max_tokens": 512,
                "tools": [{"type": "function"}],
                "tool_choice": "auto",
            },
        )

    def test_iter_sse_yields_json_chunks_and_ignores_noise(self):
        response = MagicMock()
        response.iter_lines.return_value = [
            "",
            "event: message",
            "data: {\"delta\": \"one\"}",
            "data: {\"delta\": \"two\"}",
            "data: [DONE]",
            "data: {\"delta\": \"ignored\"}",
        ]

        chunks = list(OmniaOpenAIService._iter_sse(response))

        self.assertEqual(chunks, [{"delta": "one"}, {"delta": "two"}])

    @patch("imio.omnia.core.services.fplog")
    @patch("imio.omnia.core.services.httpx.stream")
    def test_stream_completions_sets_headers_and_logs(self, mock_stream, mock_fplog):
        response = MagicMock()
        response.__enter__.return_value = response
        response.iter_lines.return_value = ["data: {\"delta\": \"one\"}", "data: [DONE]"]
        response.raise_for_status.return_value = None
        mock_stream.return_value = response
        service = OmniaOpenAIService(self.portal, self.request)
        set_setting("openai_api_url", "https://ipa.imio.be/imio/omnia/openai/v1")
        set_setting("openai_extra_headers", {"X-Test": "extra"})

        result = list(
            service._stream_completions(
                "/chat/completions",
                {"model": "gpt-test", "messages": [], "stream": True},
            )
        )

        self.assertEqual(result, [{"delta": "one"}])
        mock_stream.assert_called_once()
        _, url = mock_stream.call_args[0]
        self.assertEqual(
            url,
            "https://ipa.imio.be/imio/omnia/openai/v1/chat/completions",
        )
        self.assertEqual(
            mock_stream.call_args[1]["headers"]["Content-Type"],
            "application/json",
        )
        action, details = mock_fplog.call_args[0]
        self.assertEqual(action, "omnia.completions")
        self.assertIn("streaming=true", details)

    def test_deduce_metadata_text_only(self):
        service = OmniaCoreAPIService(self.portal, self.request)

        with patch.object(service, "send", return_value={"ok": True}) as mock_send:
            result = service.deduce_metadata(input="hello")

        self.assertEqual(result, {"ok": True})
        mock_send.assert_called_once_with(
            "POST",
            "/v1/agents/deduce-metadata",
            data={"input": "hello"},
            files=None,
        )

    def test_deduce_metadata_url_only(self):
        service = OmniaCoreAPIService(self.portal, self.request)

        with patch.object(service, "send", return_value={"ok": True}) as mock_send:
            result = service.deduce_metadata(image_url="https://example.com/image.png")

        self.assertEqual(result, {"ok": True})
        mock_send.assert_called_once_with(
            "POST",
            "/v1/agents/deduce-metadata",
            data={"image_url": "https://example.com/image.png"},
            files=None,
        )

    def test_deduce_metadata_file_upload(self):
        service = OmniaCoreAPIService(self.portal, self.request)
        image_file = object()

        with patch.object(service, "send", return_value={"ok": True}) as mock_send:
            result = service.deduce_metadata(
                input="hello",
                image_file=image_file,
            )

        self.assertEqual(result, {"ok": True})
        mock_send.assert_called_once_with(
            "POST",
            "/v1/agents/deduce-metadata",
            data={"input": "hello"},
            files={"image_file": image_file},
        )
