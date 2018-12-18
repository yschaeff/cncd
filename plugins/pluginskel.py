import logging as log
from pluginmanager import Callback

class SkeletonPlugin():
    """Inherit from this class for all Plugins"""
    NAME = "Skeleton"
    PREHOOKS = {}
    POSTHOOKS = {}
    PLUGIN_API_VERSION = 0
    HANDLES = []

    def __init__(self, datastore, gctx):
        pass

    def handle_command(self, argv, gctx, cctx, lctx):
        """must return iterable, each item will be written to connection
           as new line"""
        return

    def close(self):
        pass

