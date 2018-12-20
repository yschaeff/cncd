import logging as log
from plugins.pluginskel import SkeletonPlugin
import os, asyncio
from time import time
from collections import defaultdict

class Plugin(SkeletonPlugin):

    PLUGIN_API_VERSION = 1
    NAME = "Temperature"
    PREHOOKS = {}
    POSTHOOKS = {}
    HANDLES = []

    def __init__(self, datastore, gctx:dict):
        Plugin.POSTHOOKS = {
            ('robot', 'Device.incoming'):[self.incoming],
        }
        self.datastore = datastore

    async def incoming(self, device, response):
        handle = device.handle
        await self.datastore.update(handle, 'gcode', response)

