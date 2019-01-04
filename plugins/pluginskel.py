import logging as log
from pluginmanager import Callback, Action

# SkeletonPlugin has the minimum required functions and properties a plugin
# MUST have. It is recommended to inherit all plugins from here.

class SkeletonPlugin():
    """Inherit from this class for all Plugins"""
    NAME = "Skeleton"
    PREHOOKS = {} #of type ('MODULE', 'FUNCTION):[FUNCTION]
    POSTHOOKS = {} #of type ('MODULE', 'FUNCTION):[FUNCTION]
    PLUGIN_API_VERSION = 0
    HANDLES = [] #of type string
    ACTIONS = [] #of type Action

    def __init__(self, datastore, gctx):
        self.datastore = datastore
        self.gctx = gctx

    async def handle_command(self, gctx, cctx, lctx):
        argv = lctx.argv
        return

    def close(self):
        pass

    def __repr__(self):
        return "<{}>".format(self.NAME)
