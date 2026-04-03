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
from imio.omnia.core.settings import get_enable_openai_proxy
from imio.omnia.core.settings import get_enable_proxy
from imio.omnia.core.settings import get_openai_api_key
from imio.omnia.core.settings import get_openai_api_url
from imio.omnia.core.settings import get_openai_extra_headers
from imio.omnia.core.settings import get_organization_id
from imio.omnia.core.settings import get_setting
from imio.omnia.core.settings import set_application_id
from imio.omnia.core.settings import set_core_api_url
from imio.omnia.core.settings import set_enable_openai_proxy
from imio.omnia.core.settings import set_enable_proxy
from imio.omnia.core.settings import set_openai_api_key
from imio.omnia.core.settings import set_openai_api_url
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
            event, connection, _database = self._event_for(
                {"Application": {"Plone": site}}
            )

            sync_env_to_registry(event)

        mock_abort.assert_called_once()
        mock_exception.assert_called_once()
        self.assertEqual(mock_set_site.call_args_list[0].args, (site,))
        self.assertEqual(mock_set_site.call_args_list[-1].args, (None,))
        self.assertTrue(connection.closed)
