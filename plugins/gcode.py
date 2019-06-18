import asyncio
import time

import logging as log
from collections import defaultdict
from functools import partial
from plugins.pluginskel import SkeletonPlugin
from pluginmanager import Action
from cncd import command

class Plugin(SkeletonPlugin):

    PLUGIN_API_VERSION = 1
    NAME = "Gcode Inject Plugin"
    HANDLES = ["gcode"]
    ACTIONS = []

    def __init__(self, datastore, gctx:dict):
        super().__init__(datastore, gctx)
        cfg = self.gctx['cfg']
        self.preheated = set()

    def help(self, cmd):
        return "usage: gcode <id> <GCODE>"

    async def handle_command(self, gctx:dict, cctx:dict, lctx) -> None:
        argv = lctx.argv
        if len(lctx.argv) != 3:
            return "Specify exactly 3 arguments."
        dev_id = argv[1] ## find device handle
        cnc_devices = gctx['dev'] ## find all configured CNC devices (instances)
        if dev_id not in cnc_devices:
            return "Specified device not found"
        device = cnc_devices[dev_id]
        handle = device.handle

        gcode = argv[2]
        r = await device.inject(gcode)
        if not r: return "injection failed."

        #msg = {"progress":progress, "total":total}
        #lctx.write_json(msg)

    def close(self) -> None:
        pass

