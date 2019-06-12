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
    NAME = "Preheat Plugin"
    HANDLES = ["preheat"]
    ACTIONS = [Action("preheat i3 100", "preheat i3", "long")]

    def __init__(self, datastore, gctx:dict):
        super().__init__(datastore, gctx)
        cfg = self.gctx['cfg']
        self.preheated = set()

    def preheat(self, argv):
        handle = argv[0]
        temperature = int(argv[1])
        self.preheated.add(handle)

    async def handle_command(self, gctx:dict, cctx:dict, lctx) -> None:
        if len(lctx.argv) < 3:
            return "Not enough arguments"
        if lctx.argv[0] == 'preheat':
            self.preheat(lctx.argv[1:])

    def close(self) -> None:
        for handle in self.preheated:
            self.preheat((handle, "0"))

