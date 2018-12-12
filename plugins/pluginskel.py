import logging as log
from pluginmanager import Callback

class SkeletonPlugin():
    """Inherit from this class for all Plugins"""
    NAME = "Skeleton"
    HOOKS = {}
    PLUGIN_API_VERSION = 0

    def __init__(self, gctx):
        pass

    def handles_command(self, cmd):
        return False

    def handle_command(self, argv, gctx, cctx, lctx):
        """must return iterable, each item will be written to connection
           as new line"""
        if argv == 'skeleton':
            yield "This is not a real plugin, Don't load me."

    def close(self):
        pass

