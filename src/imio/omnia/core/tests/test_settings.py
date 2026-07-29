# -*- coding: utf-8 -*-
import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock
from unittest.mock import PropertyMock
from unittest.mock import patch

from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID

from imio.omnia.core.settings import get_application_id
from imio.omnia.core.settings import get_core_api_url
from imio.omnia.core.settings import get_core_auth_type
from imio.omnia.core.settings import get_enable_openai_proxy
from imio.omnia.core.settings import get_enable_proxy
from imio.omnia.core.settings import get_openai_api_key
from imio.omnia.core.settings import get_openai_api_url
from imio.omnia.core.settings import get_openai_auth_type
from imio.omnia.core.settings import get_openai_extra_headers
from imio.omnia.core.settings import get_organization_id
from imio.omnia.core.settings import get_setting
from imio.omnia.core.settings import set_application_id
from imio.omnia.core.settings import set_core_api_url
from imio.omnia.core.settings import set_core_auth_type
from imio.omnia.core.settings import set_enable_openai_proxy
from imio.omnia.core.settings import set_enable_proxy
from imio.omnia.core.settings import set_openai_api_key
from imio.omnia.core.settings import set_openai_api_url
from imio.omnia.core.settings import set_openai_auth_type
from imio.omnia.core.settings import set_organization_id
from imio.omnia.core.settings import set_setting
from imio.omnia.core.settings import sync_env_to_registry
from imio.omnia.core.testing import IMIO_OMNIA_CORE_INTEGRATION_TESTING


class DummyConnection:
    def __init__(self, root_object):
        self._root_object = root_object
        self.closed = False

    def root(self):
        return self._root_object

    def close(self):
        self.closed = True


class DummyDatabase:
    def __init__(self, connection):
        self.connection = connection
        self.open_calls = 0

    def open(self):
        self.open_calls += 1
        return self.connection


class DummySite:
    def __init__(self, registry):
        self._portal_registry = registry

    @property
    def portal_registry(self):
        return self._portal_registry


class TestSettingsAccessors(unittest.TestCase):
    layer = IMIO_OMNIA_CORE_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        set_core_api_url("")
        set_openai_api_url("")
        set_openai_api_key("")
        set_application_id("")
        set_organization_id("")
        set_enable_proxy(False)
        set_enable_openai_proxy(False)
        set_setting("openai_extra_headers", {})
        set_setting("core_auth_type", "none")
        set_setting("openai_auth_type", "api_key")
        set_setting("oauth_grant_type", "password")
        set_setting("oauth_client_auth_method", "client_secret_basic")
        for field in (
            "oauth_client_id",
            "oauth_client_secret",
            "oauth_token_url",
            "oauth_scope",
            "oauth_username",
            "oauth_password",
        ):
            set_setting(field, "")

    @patch("imio.omnia.core.settings.api.portal.get_registry_record")
    def test_get_setting_uses_prefixed_registry_key(self, mock_get_record):
        mock_get_record.return_value = "value"

        result = get_setting("core_api_url", default="")

        self.assertEqual(result, "value")
        mock_get_record.assert_called_once_with(
            "imio.omnia.IOmniaCoreSettings.core_api_url",
            default="",
        )

    @patch("imio.omnia.core.settings.api.portal.set_registry_record")
    def test_set_setting_uses_prefixed_registry_key(self, mock_set_record):
        set_setting("core_api_url", "https://api.example.com")

        mock_set_record.assert_called_once_with(
            "imio.omnia.IOmniaCoreSettings.core_api_url",
            "https://api.example.com",
        )

    def test_convenience_accessors_round_trip_values(self):
        cases = [
            (set_core_api_url, get_core_api_url, "https://core.example.com"),
            (set_openai_api_url, get_openai_api_url, "https://openai.example.com"),
            (set_openai_api_key, get_openai_api_key, "api-key"),
            (set_application_id, get_application_id, "omnia-app"),
            (set_organization_id, get_organization_id, "namur"),
            (set_enable_proxy, get_enable_proxy, True),
            (set_enable_openai_proxy, get_enable_openai_proxy, True),
        ]

        for setter, getter, value in cases:
            with self.subTest(getter=getter.__name__):
                setter(value)
                self.assertEqual(getter(), value)

        set_setting("openai_extra_headers", {"X-Test": "extra"})
        self.assertEqual(get_openai_extra_headers(), {"X-Test": "extra"})

    def test_core_auth_type_defaults_to_none(self):
        self.assertEqual(get_core_auth_type(), "none")

    def test_openai_auth_type_defaults_to_api_key(self):
        self.assertEqual(get_openai_auth_type(), "api_key")

    def test_core_auth_type_round_trip(self):
        set_core_auth_type("oauth2")
        self.assertEqual(get_core_auth_type(), "oauth2")
        set_core_auth_type("none")
        self.assertEqual(get_core_auth_type(), "none")

    def test_openai_auth_type_round_trip(self):
        set_openai_auth_type("oauth2")
        self.assertEqual(get_openai_auth_type(), "oauth2")
        set_openai_auth_type("none")
        self.assertEqual(get_openai_auth_type(), "none")
        set_openai_auth_type("api_key")
        self.assertEqual(get_openai_auth_type(), "api_key")

    def test_oauth_settings_round_trip(self):
        cases = [
            ("oauth_grant_type", "client_credentials"),
            ("oauth_client_id", "imio-apps-deliberationsbe"),
            ("oauth_client_secret", "s3cr3t"),
            ("oauth_token_url", "https://kc.example/realms/sso-apps/protocol/openid-connect/token"),
            ("oauth_scope", "profile"),
            ("oauth_client_auth_method", "client_secret_post"),
            ("oauth_username", "svc-account"),
            ("oauth_password", "pw"),
        ]
        for field, value in cases:
            with self.subTest(field=field):
                set_setting(field, value)
                self.assertEqual(get_setting(field), value)


class TestSyncEnvToRegistry(unittest.TestCase):
    def _event_for(self, root_object):
        connection = DummyConnection(root_object)
        database = DummyDatabase(connection)
        event = SimpleNamespace(database=database)
        return event, connection, database

    @patch.dict(os.environ, {}, clear=True)
    def test_sync_env_to_registry_returns_without_site_id(self):
        event = SimpleNamespace(database=MagicMock())

        sync_env_to_registry(event)

        event.database.open.assert_not_called()

    @patch.dict(os.environ, {"SITE_ID": "Plone"}, clear=True)
    def test_sync_env_to_registry_returns_without_env_values(self):
        event = SimpleNamespace(database=MagicMock())

        sync_env_to_registry(event)

        event.database.open.assert_not_called()

    @patch("imio.omnia.core.settings.setSite")
    @patch("imio.omnia.core.settings.transaction.commit")
    @patch.dict(
        os.environ,
        {"SITE_ID": "Plone", "OMNIA_CORE_API_URL": "https://core.example.com"},
        clear=True,
    )
    def test_sync_env_to_registry_ignores_missing_application(
        self,
        mock_commit,
        mock_set_site,
    ):
        event, connection, _database = self._event_for({})

        sync_env_to_registry(event)

        self.assertTrue(connection.closed)
        mock_commit.assert_not_called()
        self.assertEqual(mock_set_site.call_args_list[-1].args, (None,))

    @patch("imio.omnia.core.settings.logger.warning")
    @patch("imio.omnia.core.settings.setSite")
    @patch("imio.omnia.core.settings.transaction.commit")
    @patch.dict(
        os.environ,
        {"SITE_ID": "Plone", "OMNIA_CORE_API_URL": "https://core.example.com"},
        clear=True,
    )
    def test_sync_env_to_registry_warns_when_site_missing(
        self,
        mock_commit,
        mock_set_site,
        mock_warning,
    ):
        event, connection, _database = self._event_for({"Application": {}})

        sync_env_to_registry(event)

        self.assertTrue(connection.closed)
        mock_commit.assert_not_called()
        mock_warning.assert_called_once()
        self.assertEqual(mock_set_site.call_args_list[-1].args, (None,))

    @patch("imio.omnia.core.settings.setSite")
    @patch("imio.omnia.core.settings.transaction.commit")
    @patch.dict(
        os.environ,
        {
            "SITE_ID": "Plone",
            "OMNIA_CORE_API_URL": "https://core.example.com",
            "OMNIA_APPLICATION_ID": "omnia-app",
        },
        clear=True,
    )
    def test_sync_env_to_registry_updates_changed_values(
        self,
        mock_commit,
        mock_set_site,
    ):
        registry = {
            "imio.omnia.IOmniaCoreSettings.core_api_url": "https://old.example.com",
            "imio.omnia.IOmniaCoreSettings.application_id": "old-app",
        }
        site = DummySite(registry)
        event, connection, _database = self._event_for({"Application": {"Plone": site}})

        sync_env_to_registry(event)

        self.assertEqual(
            registry["imio.omnia.IOmniaCoreSettings.core_api_url"],
            "https://core.example.com",
        )
        self.assertEqual(
            registry["imio.omnia.IOmniaCoreSettings.application_id"],
            "omnia-app",
        )
        mock_commit.assert_called_once()
        self.assertEqual(mock_set_site.call_args_list[0].args, (site,))
        self.assertEqual(mock_set_site.call_args_list[-1].args, (None,))
        self.assertTrue(connection.closed)

    @patch("imio.omnia.core.settings.setSite")
    @patch("imio.omnia.core.settings.transaction.commit")
    @patch.dict(
        os.environ,
        {
            "SITE_ID": "Plone",
            "OMNIA_CORE_API_URL": "https://core.example.com",
        },
        clear=True,
    )
    def test_sync_env_to_registry_skips_commit_when_values_match(
        self,
        mock_commit,
        mock_set_site,
    ):
        registry = {
            "imio.omnia.IOmniaCoreSettings.core_api_url": "https://core.example.com",
        }
        site = DummySite(registry)
        event, connection, _database = self._event_for({"Application": {"Plone": site}})

        sync_env_to_registry(event)

        mock_commit.assert_not_called()
        self.assertEqual(mock_set_site.call_args_list[0].args, (site,))
        self.assertEqual(mock_set_site.call_args_list[-1].args, (None,))
        self.assertTrue(connection.closed)

    @patch("imio.omnia.core.settings.setSite")
    @patch("imio.omnia.core.settings.transaction.commit")
    @patch.dict(
        os.environ,
        {
            "SITE_ID": "Plone",
            "OMNIA_CORE_AUTH_TYPE": "oauth2",
            "OMNIA_OPENAI_AUTH_TYPE": "oauth2",
            "OMNIA_OAUTH_GRANT_TYPE": "password",
            "SSO_APPS_CLIENT_ID": "my-client",
            "SSO_APPS_CLIENT_SECRET": "my-secret",
            "SSO_APPS_URL": "https://kc.example/token",
            "OMNIA_OAUTH_SCOPE": "profile",
            "OMNIA_OAUTH_CLIENT_AUTH_METHOD": "client_secret_post",
            "SSO_APPS_USER_USERNAME": "svc",
            "SSO_APPS_USER_PASSWORD": "pw",
        },
        clear=True,
    )
    def test_sync_env_to_registry_syncs_oauth_settings(self, mock_commit, mock_set_site):
        prefix = "imio.omnia.IOmniaCoreSettings"
        registry = {
            f"{prefix}.core_auth_type": "none",
            f"{prefix}.openai_auth_type": "api_key",
            f"{prefix}.oauth_grant_type": "password",
            f"{prefix}.oauth_client_id": "",
            f"{prefix}.oauth_client_secret": "",
            f"{prefix}.oauth_token_url": "",
            f"{prefix}.oauth_scope": "",
            f"{prefix}.oauth_client_auth_method": "client_secret_basic",
            f"{prefix}.oauth_username": "",
            f"{prefix}.oauth_password": "",
        }
        site = DummySite(registry)
        event, connection, _database = self._event_for({"Application": {"Plone": site}})

        sync_env_to_registry(event)

        self.assertEqual(registry[f"{prefix}.core_auth_type"], "oauth2")
        self.assertEqual(registry[f"{prefix}.openai_auth_type"], "oauth2")
        self.assertEqual(registry[f"{prefix}.oauth_client_id"], "my-client")
        self.assertEqual(registry[f"{prefix}.oauth_client_auth_method"], "client_secret_post")
        self.assertEqual(registry[f"{prefix}.oauth_password"], "pw")
        mock_commit.assert_called_once()
        self.assertTrue(connection.closed)

    @patch("imio.omnia.core.settings.logger.exception")
    @patch("imio.omnia.core.settings.transaction.abort")
    @patch("imio.omnia.core.settings.setSite")
    @patch.dict(
        os.environ,
        {"SITE_ID": "Plone", "OMNIA_CORE_API_URL": "https://core.example.com"},
        clear=True,
    )
    def test_sync_env_to_registry_aborts_and_logs_on_failure(
        self,
        mock_set_site,
        mock_abort,
        mock_exception,
    ):
        registry = {"imio.omnia.IOmniaCoreSettings.core_api_url": "old"}
        site = DummySite(registry)
        with patch.object(
            DummySite,
            "portal_registry",
            new_callable=PropertyMock,
            side_effect=RuntimeError("broken registry"),
        ):
            event, connection, _database = self._event_for({"Application": {"Plone": site}})

            sync_env_to_registry(event)

        mock_abort.assert_called_once()
        mock_exception.assert_called_once()
        self.assertEqual(mock_set_site.call_args_list[0].args, (site,))
        self.assertEqual(mock_set_site.call_args_list[-1].args, (None,))
        self.assertTrue(connection.closed)
