from zope.component import adapter
from zope.interface import Interface, implementer

from imio.omnia.core.interfaces import IOrganizationIDProvider
from imio.omnia.core.settings import get_organization_id


@adapter(Interface)
@implementer(IOrganizationIDProvider)
class OrganizationIDProvider:
    """Default provider: returns the organization ID from the Plone registry."""

    def __init__(self, context):
        self.context = context

    def __call__(self):
        return get_organization_id()
