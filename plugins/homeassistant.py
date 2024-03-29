import logging as log
from plugins.pluginskel import SkeletonPlugin, ConfigPlugin
import os, asyncio, re, concurrent, traceback
from time import time
from collections import defaultdict
from requests import post
from time import time


class Plugin(SkeletonPlugin, ConfigPlugin):

    PLUGIN_API_VERSION = 1
    NAME = "Home Assistant"
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
            ('robot', 'Device.gcode_open_hook'):[self.gcode_open_hook],
            ('robot', 'Device.gcode_done_hook'):[self.gcode_done_hook],
            ('datastore', 'DataStore.update'):[self.datastore_update],
        }
        self.ratelimit = {}

        cfg = self.config('homeassistant')
        if not cfg:
            log.error("Home Assistant plugin loaded but no configuration available.")
        self.token = cfg['token']
        self.url = cfg['url']
        self.limit = int(cfg['limit'])

    def ha_sanitize(value):
        return value.replace("@", "at")

    def send(self, device, entity, data, binary=False):
        entity = Plugin.ha_sanitize(entity)
        sensor = ["sensor", "binary_sensor"][binary]
        url = f"{self.url}/{sensor}.cncd_{device.handle}_{entity}"
        headers = {"Authorization": f"Bearer {self.token}", "content-type": "application/json"}
        log.info(f"sending {data}")
        try:
            post(url, headers=headers, json=data)
        except Exception as e:
            log.error(f"Failed to send data to home assistant {e}")

    def send_binary(self, device, entity, data):
        self.send(device, entity, data, binary=True)

    def send_temperature(self, device, entity, value):
        entity = f"temperature_{entity}"
        data = {"attributes":
                  {
                    "friendly_name":       f"{device.get_name()} {entity}",
                    "state_class":          "measurement",
                    "unit_of_measurement":  "°C",
                  },
                  "state": value
                }
        self.send(device, entity, data)

    def ratelimiter(self, handle):
        now = time()
        if not handle in self.ratelimit or now - self.ratelimit[handle] > self.limit:
            self.ratelimit[handle] = now
            return True
        return False

    async def datastore_update(self, datastore, handle, name, value):
        # we can't do this sens async yet. So better not update to often
        if name == "temperature_obj":
            if not self.ratelimiter(f"{handle}_temperature"): return
            device = self.gctx['dev'][handle]
            for T in value:
                entity, d = T.split(":")
                ts = d.split(" /")
                self.send_temperature(device, f"{entity}", ts[0])
                if len(ts) > 1:
                    self.send_temperature(device, f"set_{entity}", ts[1])
        elif name == "progress": #filesize
            progress = value
            total = self.datastore.get(handle, "filesize")
            if progress != total and not self.ratelimiter(f"{handle}_progress"): return
            device = self.gctx['dev'][handle]
            pct = 0
            try:
                pct = int(progress/total * 10000)/100
            except ZeroDivisionError:
                pass
            self.send(device, "progress", {"state": pct, "attributes":{"state_class":"measurement", "unit_of_measurement":"%"}})
        else:
            pass

    async def connect(self, device):
        ## I think this is only called on successful connect
        #connected = self.datastore.get(device.handle, "connected")
        #if not connected: return
        self.send_binary(device, "connected", {"state": "on"})

    async def disconnect(self, device, exc):
        self.send_binary(device, "connected", {"state": "off"})

    async def gcode_open_hook(self, device, filename):
        fn_s = filename.rfind("/") + 1
        fn_e = filename.rfind(".")
        fn = filename[fn_s:fn_e]
        self.send(device, "filename", {"state": fn})
        self.send_binary(device, "active", {"state": "on"})

    async def gcode_done_hook(self, device):
        self.send_binary(device, "active", {"state": "off"})
