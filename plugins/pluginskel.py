import logging as log
from pluginmanager import Callback, Action
from collections import defaultdict

# SkeletonPlugin has the minimum required functions and properties a plugin
# MUST have. It is recommended to inherit all plugins from here.

class PrivateStore:
    """ structure to store data for this plugib only """
    def __init__(self):
        self.devs = defaultdict(dict)
    def update(self, handle, key, value):
        self.devs[handle][key] = value
    def inc(self, handle, key, value):
        self.devs[handle][key] += value
    def get(self, handle, key):
        return self.devs[handle][key]

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
        self.localstore = PrivateStore()
        self.gctx = gctx

    async def handle_command(self, gctx, cctx, lctx):
        argv = lctx.argv
        return

    def close(self):
        pass

    def __repr__(self):
        return "<{}>".format(self.NAME)

class ConfigPlugin():
    def config(self, name):
        cfg = self.gctx['cfg']
        if name in cfg:
            return cfg[name]
        else:
            return None
