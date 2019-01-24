import logging as log
from plugins.pluginskel import SkeletonPlugin
import asyncio

class Plugin(SkeletonPlugin):
    PLUGIN_API_VERSION = 1
    NAME = "Plugin Lister"
    HANDLES = ['plugins']

    def __init__(self, datastore, gctx:dict):
        super().__init__(datastore, gctx)
        handles = " ".join(['"{}"'.format(plugin.NAME) for plugin in gctx['plugins']])
        asyncio.ensure_future(datastore.update('general', 'plugins', handles))

    async def handle_command(self, gctx:dict, cctx:dict, lctx) -> None:
        plugins = gctx['plugins']
        msg = {}
        for plugin in plugins:
            msg[plugin.NAME] = plugin.HANDLES
        lctx.write_json(msg)

