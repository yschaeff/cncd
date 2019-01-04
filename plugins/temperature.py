import logging as log
from plugins.pluginskel import SkeletonPlugin
import os, asyncio, re, concurrent, traceback
from time import time
from collections import defaultdict

class Plugin(SkeletonPlugin):

    PLUGIN_API_VERSION = 1
    NAME = "Temperature"
    PREHOOKS = {}
    POSTHOOKS = {}
    HANDLES = []

    def __init__(self, datastore, gctx:dict):
        super().__init__(datastore, gctx)
        Plugin.PREHOOKS = {
            ('robot', 'Device.disconnect_done'):[self.disconnect],
        }
        Plugin.POSTHOOKS = {
            ('robot', 'Device.connect_done'):[self.connect],
            ('robot', 'Device.rx_hook'):[self.incoming],
        }
        self.tasks_by_handle = {}
        self.tmp_pttrn = re.compile(r"[^\s:]+:\d+(?:\.\d+)?(?: /\d+(?:\.\d+)?)?")

    
    def poll_cb(self, future):
        """Generic callback for tasks"""
        try:
            r = future.result()
        except concurrent.futures._base.CancelledError:
            pass
        except Exception as e:
            log.critical(str(e))
            log.critical(traceback.format_exc())

    async def poll(self, device):
        handle = device.handle
        while True:
            if not await device.inject('M105'):
                log.warning("Sending time probe failed. Backing off")
                break
            await self.datastore.update(handle, "last_temp_request", time())
            await asyncio.sleep(3)

    async def connect(self, device):
        handle = device.handle
        if handle in self.tasks_by_handle:
            return
        connected = self.datastore.get(handle, "connected")
        if not connected:
            return 
        await self.datastore.update(handle, "last_temp_request", 0)
        task = asyncio.ensure_future(self.poll(device))
        task.add_done_callback(self.poll_cb)
        ## TODO add exception handler
        self.tasks_by_handle[handle] = task

    async def disconnect(self, device, exc):
        task = self.tasks_by_handle.pop(device.handle, None)
        if task:
            task.cancel()

    async def incoming(self, device, response):
        handle = device.handle
        groups = self.tmp_pttrn.findall(response)
        if groups:
            await self.datastore.update(handle, "temperature", str(groups))
