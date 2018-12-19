import logging as log
from plugins.pluginskel import SkeletonPlugin
import os, asyncio
from time import time
from collections import defaultdict

class Plugin(SkeletonPlugin):

    PLUGIN_API_VERSION = 1
    NAME = "Log forwarder"
    PREHOOKS = {}
    POSTHOOKS = {}
    HANDLES = ['tracedev']

    def __init__(self, datastore, gctx:dict):
        Plugin.POSTHOOKS = {
            ('datastore', 'DataStore.update_device'):[self.update_device],
        }
        self.events = {}

    async def update_device(self, store, devicename, name, value):
        if devicename not in self.events:
            return
        event, writeln = self.events[devicename]
        writeln('"{}":"{}"'.format(name, value))

    async def handle_command(self, gctx:dict, cctx:dict, lctx) -> None:
        argv = lctx.argv
        if len(argv) < 3 or (argv[1] != 'start' and argv[1] != 'stop'):
            lctx.writeln("ERROR specify start or stop and device")
            return
        handle = argv[2]
        if argv[1] == 'start':
            if handle in self.events:
                event, writeln = self.events[handle]
                event.set()
            event = asyncio.Event()
            self.events[handle] = (event, lctx.writeln)
            event.clear()
            await event.wait()
            self.events.pop(handle)
        else:
            if handle in self.events:
                event, writeln = self.events[handle]
                event.set()

    def close(self) -> None:
        for event, writeln in self.events.values():
            event.set()

