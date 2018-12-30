import logging as log
from plugins.pluginskel import SkeletonPlugin
import asyncio

class Plugin(SkeletonPlugin):
    PLUGIN_API_VERSION = 1
    NAME = "Plugin lister"
    HANDLES = ['plugins']

    def __init__(self, datastore, gctx:dict):
        super().__init__(datastore, gctx)
        handles = " ".join(['"{}"'.format(plugin.NAME) for plugin in gctx['plugins']])
        asyncio.ensure_future(datastore.update('general', 'plugins', handles))

    async def handle_command(self, gctx:dict, cctx:dict, lctx) -> None:
        plugins = gctx['plugins']
        for plugin in plugins:
            handles = ",".join(['"{}"'.format(cmd) for cmd in plugin.HANDLES])
            lctx.writeln('"{}":{}'.format(plugin.NAME, handles))

