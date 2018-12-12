import logging as log
from plugins.pluginskel import SkeletonPlugin
import os
from collections import defaultdict

## Keeps track of the progress in de gcode file
## This plugin should be a model to other plugins and will therefore have
## extensive comments.

class Plugin(SkeletonPlugin):
    PLUGIN_API_VERSION = 1
    NAME = "Progress plugin"
    PREHOOKS = {}
    POSTHOOKS = {}
    HANDLES = ['progress']

    def __init__(self, gctx:dict):
        Plugin.POSTHOOKS = {
            ('robot', 'Device.gcode_open_hook'):[self.open_cb],
            ('robot', 'Device.gcode_readline_hook'):[self.readline_cb],
        }
        self.gctx = gctx
        class Progress:
            def __init__(self):
                self.progress = 0
                self.total = 0
            def __repr__(self):
                return "{}/{}".format(self.progress, self.total)
        self.devices = defaultdict(Progress)
        self.total = 0
        self.read = 0

    async def open_cb(self, module:str, qname:str, *args, **kwargs) -> None:
        device, filename = args
        self.devices[device].total = os.path.getsize(filename)

    async def readline_cb(self, module:str, qname:str, *args, **kwargs) -> None:
        device, line = args
        self.devices[device].progress += len(line)

    def handle_command(self, argv:list, gctx:dict, cctx:dict, lctx) -> None:
        """must return iterable, each item will be written to connection
           as new line"""
        if len(argv) < 2:
            yield "ERROR Must specify device"
            return
        dev_id = argv[1]
        cnc_devices = gctx['dev']
        if dev_id not in cnc_devices:
            yield "ERROR Specified device not found"
            return
        device = cnc_devices[dev_id]
        progress = self.devices[device]
        yield str(progress)

    def close(self) -> None:
        pass


