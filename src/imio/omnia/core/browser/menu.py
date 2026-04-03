from plone.app.contentmenu.interfaces import IActionsMenu, IActionsSubMenuItem
from plone.protect.utils import addTokenToUrl
from zope.browsermenu.interfaces import IBrowserMenu
from zope.browsermenu.menu import BrowserMenu, BrowserSubMenuItem
from zope.component import getMultiAdapter, getAllUtilitiesRegisteredFor, getUtility
from zope.interface import implementer
from imio.omnia.core.interfaces import IOmniaActionsProvider
from imio.omnia.core import _

class IOmniaActionsMenu(IBrowserMenu):
    """The menu item linking to the actions menu."""


@implementer(IActionsSubMenuItem)
class OmniaActionsSubMenuItem(BrowserSubMenuItem):
    title = _("omnia_actions", default="AI assistant")
    description = _(
        "title_actions_menu", default="Actions for the current content item"
    )
    submenuId = "omnia-ai-actions"
    icon = "omnia.monochrome.light"
    order = 60
    extra = {
        "id": "plone-omnia-actions",
        "li_class": "plonetoolbar-omnia-action",
    }

    def __init__(self, context, request):
        super().__init__(context, request)
        self.context_state = getMultiAdapter(
            (context, request), name="plone_context_state"
        )

    @property
    def action(self):
        return "#"

    def available(self):
        menu = getUtility(IBrowserMenu, name=self.submenuId)
        return bool(menu.getMenuItems(self.context, self.request))

    def selected(self):
        return False


@implementer(IOmniaActionsMenu)
class OmniaActionsMenu(BrowserMenu):


    def getMenuItems(self, context, request):
        """Return menu item entries in a TAL-friendly form."""
        results = []
        context_state = getMultiAdapter((context, request), name="plone_context_state")
        omnia_actions = context_state.actions("omnia_actions")
        for action in omnia_actions:
            if not action["allowed"]:
                continue
            aid = action["id"]
            cssClass = f"actionicon-object_buttons-{aid}"
            icon = action.get("icon", None)
            modal = action.get("modal", None)
            if modal:
                cssClass += " pat-plone-modal"

            results.append(
                {
                    "title": action["title"],
                    "description": action.get("description", ""),
                    "action": addTokenToUrl(action["url"], request),
                    "selected": False,
                    "icon": icon,
                    "extra": {
                        "id": "plone-contentmenu-actions-" + aid,
                        "separator": None,
                        "class": cssClass,
                        "modal": modal,
                    },
                    "submenu": None,
                }
            )

        addon_actions_providers = getAllUtilitiesRegisteredFor(IOmniaActionsProvider)
        for actions_provider in addon_actions_providers:
            for action in actions_provider(context, request):
                results.append(action)
        return results
