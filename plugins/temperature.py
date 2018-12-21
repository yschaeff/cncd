import logging as log
from plugins.pluginskel import SkeletonPlugin
import os, asyncio, re
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
            ('robot', 'Device.disconnect'):[self.disconnect],
        }
        Plugin.POSTHOOKS = {
            ('robot', 'Device.connect'):[self.connect],
            ('robot', 'Device.incoming'):[self.incoming],
        }
        self.datastore = datastore
        self.tasks_by_handle = {}
        self.tmp_pttrn = re.compile(r"\S+:\S+(?: /\S+)?")

    async def poll(self, device):
        handle = device.handle
        await asyncio.sleep(5)
        while True:
            await device.inject('M105')
            await self.datastore.update(handle, "last_temp_request", time())
            await asyncio.sleep(3)

    async def connect(self, device):
        handle = device.handle
        await self.datastore.update(handle, "last_temp_request", 0)
        task = asyncio.ensure_future(self.poll(device))
        self.tasks_by_handle[handle] = task

    async def disconnect(self, device):
        task = self.tasks_by_handle.get(device.handle, None)
        if task:
            task.cancel()

    async def incoming(self, device, response):
        handle = device.handle
        #await self.datastore.update(handle, "response", response)
        groups = self.tmp_pttrn.findall(response)
        if groups:
            await self.datastore.update(handle, "temperature", response, str(groups))
        #for group in groups:
            #l = group.split()
            #label = "?"
            #for i in l:
                #index = i.find(':')
                #if index != -1:
                    #label = i[:index]
                    #data = i[index+1:]
                #else:
                    #label += " set"
                    #data = i[1:]
                #await self.datastore.update(handle, label, data)


