# -*- coding: utf-8 -*-
"""Setup tests for this package."""
import unittest

from plone import api
from plone.app.testing import logout
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from imio.omnia.core.testing import IMIO_OMNIA_CORE_INTEGRATION_TESTING  # noqa: E501


try:
    from Products.CMFPlone.utils import get_installer
except ImportError:
    get_installer = None


OMNIA_API_PROXY_PERMISSION = "imio.omnia.core: Access Omnia API proxy"
OMNIA_OPENAI_PROXY_PERMISSION = "imio.omnia.core: Access Omnia OpenAI proxy"


def selected_roles_for_permission(portal, permission):
    roles = portal.rolesOfPermission(permission)
    return [role["name"] for role in roles if role["selected"]]


def registered_permissions(portal):
    return [permission[0] for permission in portal.ac_inherited_permissions(1)]


class TestSetup(unittest.TestCase):
    """Test that imio.omnia.core is properly installed."""

    layer = IMIO_OMNIA_CORE_INTEGRATION_TESTING

    def setUp(self):
        """Custom shared utility setup for tests."""
        self.portal = self.layer['portal']
        if get_installer:
            self.installer = get_installer(self.portal, self.layer['request'])
        else:
            self.installer = api.portal.get_tool('portal_quickinstaller')

    def test_product_installed(self):
        """Test if imio.omnia.core is installed."""
        self.assertTrue(self.installer.is_product_installed(
            'imio.omnia.core'))

    def test_browserlayer(self):
        """Test that IImioOmniaCoreLayer is registered."""
        from imio.omnia.core.interfaces import (
            IImioOmniaCoreLayer)
        from plone.browserlayer import utils
        self.assertIn(
            IImioOmniaCoreLayer,
            utils.registered_layers())

    def test_omnia_api_proxy_permission_registered(self):
        """The Omnia API proxy permission is registered on the portal."""
        self.assertIn(
            OMNIA_API_PROXY_PERMISSION,
            registered_permissions(self.portal),
        )

    def test_omnia_openai_proxy_permission_registered(self):
        """The OpenAI proxy permission is registered on the portal."""
        self.assertIn(
            OMNIA_OPENAI_PROXY_PERMISSION,
            registered_permissions(self.portal),
        )

    def test_omnia_api_proxy_permission_roles(self):
        """The Omnia API proxy permission is granted to Authenticated only."""
        roles = selected_roles_for_permission(
            self.portal,
            OMNIA_API_PROXY_PERMISSION,
        )
        self.assertListEqual(roles, ["Authenticated"])

    def test_omnia_openai_proxy_permission_roles(self):
        """The OpenAI proxy permission is granted to Authenticated only."""
        roles = selected_roles_for_permission(
            self.portal,
            OMNIA_OPENAI_PROXY_PERMISSION,
        )
        self.assertListEqual(roles, ["Authenticated"])

    def test_anonymous_lacks_proxy_permissions_by_default(self):
        """Anonymous does not get either proxy permission in the core profile."""
        self.assertNotIn(
            "Anonymous",
            selected_roles_for_permission(
                self.portal,
                OMNIA_API_PROXY_PERMISSION,
            ),
        )
        self.assertNotIn(
            "Anonymous",
            selected_roles_for_permission(
                self.portal,
                OMNIA_OPENAI_PROXY_PERMISSION,
            ),
        )

    def test_openai_proxy_permission_can_be_overridden(self):
        """Projects can grant the OpenAI proxy permission to Anonymous."""
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        self.portal.manage_permission(
            OMNIA_OPENAI_PROXY_PERMISSION,
            roles=["Anonymous", "Authenticated"],
            acquire=0,
        )

        roles = selected_roles_for_permission(
            self.portal,
            OMNIA_OPENAI_PROXY_PERMISSION,
        )
        self.assertListEqual(roles, ["Anonymous", "Authenticated"])
        logout()
        self.assertTrue(
            api.user.has_permission(
                OMNIA_OPENAI_PROXY_PERMISSION,
                obj=self.portal,
            )
        )


class TestUninstall(unittest.TestCase):

    layer = IMIO_OMNIA_CORE_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        if get_installer:
            self.installer = get_installer(self.portal, self.layer['request'])
        else:
            self.installer = api.portal.get_tool('portal_quickinstaller')
        roles_before = api.user.get_roles(TEST_USER_ID)
        setRoles(self.portal, TEST_USER_ID, ['Manager'])
        self.installer.uninstall_product('imio.omnia.core')
        setRoles(self.portal, TEST_USER_ID, roles_before)

    def test_product_uninstalled(self):
        """Test if imio.omnia.core is cleanly uninstalled."""
        self.assertFalse(self.installer.is_product_installed(
            'imio.omnia.core'))

    def test_browserlayer_removed(self):
        """Test that IImioOmniaCoreLayer is removed."""
        from imio.omnia.core.interfaces import \
            IImioOmniaCoreLayer
        from plone.browserlayer import utils
        self.assertNotIn(IImioOmniaCoreLayer, utils.registered_layers())
