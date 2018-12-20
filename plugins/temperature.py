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
        Plugin.PREHOOKS = {
            ('robot', 'Device.start'):[self.connect],
        }
        Plugin.POSTHOOKS = {
            ('robot', 'Device.incoming'):[self.incoming],
            #('robot', 'Device.connect'):[self.connect],
            #('robot', 'Device.start'):[self.connect],
        }
        self.datastore = datastore

    async def connect(self, device):
        await device.send('M155 S1', wait_for_ack=False)

    async def incoming(self, device, response):
        handle = device.handle
        await self.datastore.update(handle, 'response', response)
        ## does it look like a temperature message?
        if response.startswith('T:'):
            ## likely. Lets just try it and bail on failure
            try:
                chunks = response.split(" ")
                for chunk in chunks:
                    c = chunk.split(":")
                    L, T = c[0], c[1]
                    await self.datastore.update(handle, L, T)
            except:
                log.debug("failed to parse, maybe not tmp msg?")


