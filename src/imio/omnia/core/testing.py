# -*- coding: utf-8 -*-
from plone.app.robotframework.testing import REMOTE_LIBRARY_BUNDLE_FIXTURE
from plone.app.testing import (
    applyProfile,
    FunctionalTesting,
    IntegrationTesting,
    PLONE_FIXTURE,
    PloneSandboxLayer,
)
from plone.testing import z2

import imio.omnia.core


class ImioOmniaCoreLayer(PloneSandboxLayer):

    defaultBases = (PLONE_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        # Load any other ZCML that is required for your tests.
        # The z3c.autoinclude feature is disabled in the Plone fixture base
        # layer.
        import plone.app.dexterity
        self.loadZCML(package=plone.app.dexterity)
        import plone.restapi
        self.loadZCML(package=plone.restapi)
        self.loadZCML(package=imio.omnia.core)

    def setUpPloneSite(self, portal):
        applyProfile(portal, 'imio.omnia.core:default')


IMIO_OMNIA_CORE_FIXTURE = ImioOmniaCoreLayer()


IMIO_OMNIA_CORE_INTEGRATION_TESTING = IntegrationTesting(
    bases=(IMIO_OMNIA_CORE_FIXTURE,),
    name='ImioOmniaCoreLayer:IntegrationTesting',
)


IMIO_OMNIA_CORE_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(IMIO_OMNIA_CORE_FIXTURE,),
    name='ImioOmniaCoreLayer:FunctionalTesting',
)


IMIO_OMNIA_CORE_ACCEPTANCE_TESTING = FunctionalTesting(
    bases=(
        IMIO_OMNIA_CORE_FIXTURE,
        REMOTE_LIBRARY_BUNDLE_FIXTURE,
        z2.ZSERVER_FIXTURE,
    ),
    name='ImioOmniaCoreLayer:AcceptanceTesting',
)
