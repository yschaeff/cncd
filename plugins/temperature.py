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
            ('robot', 'Device.connect'):[self.connect],
        }
        Plugin.POSTHOOKS = {
            ('robot', 'Device.incoming'):[self.incoming],
        }
        self.datastore = datastore

    async def poll(self, device):
        while True:
            await device.inject('M105')
            asyncio.sleep(3)

    async def poll_start(self, device):
        #asyncio ensure
        #save task
        pass
    async def poll_stop(self, device):
        #get poll task for device
        #task.cancel()
        pass

    async def connect(self, device):
        handle = device.handle
        await self.datastore.update(handle, "last_temp_request", 0)

    async def incoming(self, device, response):
        handle = device.handle

        ##beter yet, on connect start a reocuring task and on disconnect stop it.
        last_temp = self.datastore.get(handle, "last_temp_request")
        now = time()
        if now - last_temp > 2:
            ## request temp report
            ## Don't wait for it, the code would deadlock.
            asyncio.ensure_future(device.inject('M105'))
            await self.datastore.update(handle, "last_temp_request", time())

        #'ok T:22.5 /0.0 B:22.6 /0.0 T0:22.5 /0.0 @:0 B@:0'
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


