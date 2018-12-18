import logging as log
from plugins.pluginskel import SkeletonPlugin

class Plugin(SkeletonPlugin):
    PLUGIN_API_VERSION = 1
    NAME = "Plugin lister"
    HANDLES = ['plugins']

    def handle_command(self, argv:list, gctx:dict, cctx:dict, lctx) -> None:
        plugins = gctx['plugins']
        for plugin in plugins:
            handles = ",".join(['"{}"'.format(cmd) for cmd in plugin.HANDLES])
            yield '"{}":{}'.format(plugin.NAME, handles)

