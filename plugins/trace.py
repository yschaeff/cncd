import logging as log
from plugins.pluginskel import SkeletonPlugin
import os, asyncio
from time import time
from collections import defaultdict

class Plugin(SkeletonPlugin):

    PLUGIN_API_VERSION = 1
    NAME = "Data Subscriber"
    PREHOOKS = {}
    POSTHOOKS = {}
    HANDLES = ['subscribe', 'unsubscribe']

    def __init__(self, datastore, gctx:dict):
        super().__init__(datastore, gctx)
        Plugin.POSTHOOKS = {
            ('datastore', 'DataStore.update'):[self.update],
        }
        self.handles = defaultdict(dict)

    async def update(self, store, devicename, name, value):
        listeners_for_handle = self.handles[devicename]
        for con, (event, writeln) in listeners_for_handle.items():
            writeln('"{}":"{}"'.format(name, value))

    async def handle_command(self, gctx:dict, cctx:dict, lctx) -> None:
        argv = lctx.argv
        if len(argv) < 2:
            lctx.writeln("ERROR specify what to subscribe to")
            return
        handle = argv[1]
        listeners_for_handle = self.handles[handle]
        key = cctx['transport']
        if argv[0] == 'subscribe':
            if key in listeners_for_handle:
                event, writeln = listeners_for_handle[key]
                event.set()
            event = asyncio.Event()
            listeners_for_handle[key] = (event, lctx.writeln)
            event.clear()
            await event.wait()
            listeners_for_handle.pop(key)
        else:
            if key in listeners_for_handle:
                event, writeln = listeners_for_handle[key]
                event.set()

