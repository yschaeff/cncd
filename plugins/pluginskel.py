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
        self.datastore = datastore
        self.gctx = gctx

    async def handle_command(self, gctx, cctx, lctx):
        argv = lctx.argv
        return

    def close(self):
        pass

