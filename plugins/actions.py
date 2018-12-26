import logging as log
from pluginmanager import Action
from plugins.pluginskel import SkeletonPlugin

class Plugin(SkeletonPlugin):
    """Inherit from this class for all Plugins"""
    NAME = "Action"
    PLUGIN_API_VERSION = 0
    HANDLES = ["actions"] #of type string

    async def handle_command(self, gctx, cctx, lctx):
        pluginmanager = gctx['pluginmanager']
        actions = pluginmanager.get_actions()
        for cmd, short, long in actions:
            lctx.writeln('"{}" "{}" "{}"'.format(cmd, short, long))

