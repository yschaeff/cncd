import logging as log
from plugins.pluginskel import SkeletonPlugin

class Plugin(SkeletonPlugin):
    PLUGIN_API_VERSION = 1
    NAME = "Data"
    HANDLES = ['data']

    async def handle_command(self, gctx:dict, cctx:dict, lctx) -> None:
        argv = lctx.argv
        if len(argv) <= 1:
            lctx.writeln("ERROR need more args")
            return
        handle = argv[1]
        for key, value in self.datastore.data[handle].items():
            lctx.writeln('"{}":"{}"'.format(key, value))

