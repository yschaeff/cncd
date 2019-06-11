import logging as log
from plugins.pluginskel import SkeletonPlugin
import os, re, asyncio
from time import time

## Keeps track of the progress in de gcode file
## This plugin should be a model to other plugins and will therefore have
## extensive comments.

## A class Plugin MUST be present in this file
## You are recommended to inherit from the SkeletonPlugin. So that when new
## properties are introduced in the future your plugin keeps working.
class Plugin(SkeletonPlugin):

    ## Version of the API this plugin was written for. In the future this will
    ## be used to make sure the plugin is compatible before loading.
    PLUGIN_API_VERSION = 1
    ## Name of the plugin, take your pick. Mainly used for logging.
    NAME = "Progress plugin"
    ## The hooks this plugin request on the main code. More on syntax below.
    ## PREHOOKS are executed before the command it hooks in to, and POSTHOOKS
    ## after.
    PREHOOKS = {}
    POSTHOOKS = {}
    ## HANDLES defines which user commands are handled by this plugin. If
    ## HANDLES is not empty the handle_command() function MUST exist.
    HANDLES = ['progress']


    ## starting point for every plugin. Passed is gctx which stand for 
    ## global context. It includes configuration, listening sockets etc.
    ## You SHOULD not write to gctx.
    ## It also gets passed a datastore. We are allowed to write information
    ## to it that is relevant for the end user and/or other plugins.
    def __init__(self, datastore, gctx:dict):
        super().__init__(datastore, gctx)
        ## We define our actions as POSTHOOKS here. We do not need to do
        ## anything beforehand in this case.
        ## 
        ## The key is a tuple (module, class.function). In this case the
        ## function is called gcode_open_hook of the Device class. and it is
        ## located in the robot module (robot.py).
        ## The tuple is not check for existance. If it doesn't exist it will
        ## simply never be called.
        ##
        ## The value is a list of functions that serve as callbacks. The
        ## arguments to these functions are the original arguments to the
        ## hooked function.
        Plugin.POSTHOOKS = {
            ('robot', 'Device.gcode_open_hook'):[self.open_cb],
            ('robot', 'Device.gcode_readline_hook'):[self.readline_cb],
            ('robot', 'Device.gcode_done_hook'):[self.done_cb],
        }

        self.g_pattern = re.compile(r"(?:\s+([XYZEF])\s*(-?\d*(?:\.\d+)?))")

    ## Specifically defined for this plugin. However the function signature is
    ## important. The function MUST be defined async. Because CNCD is single
    ## threaded it is super important to NOT DO ANY LONG OPERATIONS here. If
    ## you ABSOLUTELY must then occasionally "await asyncio.sleep(0)" to handle
    ## control back to the scheduler for a bit.
    ## Make sure the function signature is compatible with the function hooked.
    async def open_cb(self, *args, **kwargs) -> None:
        device, filename = args
        handle = device.handle
        try:
            size = os.path.getsize(filename)
        except FileNotFoundError:
            size = -1
        ## For the datastore the convention is to store all device specific
        ## information with device.handle as key. System wide should
        ## use 'general'
        await self.datastore.update(handle, "starttime", time())
        await self.datastore.update(handle, "stoptime", -1)
        await self.datastore.update(handle, "filename", filename)
        await self.datastore.update(handle, "filesize", size)
        await self.datastore.update(handle, "progress", 0)
        self.localstore.update(handle, 'accumulate', 0)
        self.localstore.update(handle, 'last_update', 0)

        await self.datastore.update(handle, "current_e", 0)
        await self.datastore.update(handle, "current_z", 0)
        await self.datastore.update(handle, "final_e", 1)
        await self.datastore.update(handle, "final_z", 1)
        self.localstore.update(handle, 'E', 0)
        self.localstore.update(handle, 'Z', 0)
        self.localstore.update(handle, 'E_push', 0)
        self.localstore.update(handle, 'Z_push', 0)
        self.localstore.update(handle, 'absE', False)
        self.localstore.update(handle, 'absXYZ', False)

        asyncio.ensure_future(self.analyse_gcode(handle, filename))

    def process_line(self, handle, line, pfx=""):
        if line.startswith('M82'):
            self.localstore.update(handle, pfx+'absE', True)
        elif line.startswith('M83'):
            self.localstore.update(handle, pfx+'absE', False)
        elif line.startswith('G90'):
            self.localstore.update(handle, pfx+'absE', True)
            self.localstore.update(handle, pfx+'absXYZ', True)
        elif line.startswith('G91'):
            self.localstore.update(handle, pfx+'absE', False)
            self.localstore.update(handle, pfx+'absXYZ', False)
        elif line.startswith('G0') or line.startswith('G1'):
            d = self.parseG(self.g_pattern, line)
            if 'Z' in d:
                if self.localstore.get(handle, pfx+'absXYZ'):
                    self.localstore.update(handle, pfx+'Z', d['Z'])
                else:
                    self.localstore.inc(handle, pfx+'Z', d['Z'])
            if 'E' in d:
                if self.localstore.get(handle, pfx+'absE'):
                    self.localstore.update(handle, pfx+'E', d['E'])
                else:
                    self.localstore.inc(handle, pfx+'E', d['E'])
        elif line.startswith('G92'):
            #set absolute positions
            d = self.parseG(self.g_pattern, line)
            if 'Z' in d:
                self.localstore.inc(handle, pfx+'Z_push', self.localstore.get(handle, pfx+'Z'))
                self.localstore.update(handle, pfx+'Z', d['Z'])
            if 'E' in d:
                self.localstore.inc(handle, pfx+'E_push', self.localstore.get(handle, pfx+'E'))
                self.localstore.update(handle, pfx+'E', d['E'])

    async def analyse_gcode(self, handle, filename):
        self.localstore.update(handle, 'init_E', 0)
        self.localstore.update(handle, 'init_Z', 0)
        self.localstore.update(handle, 'init_E_push', 0)
        self.localstore.update(handle, 'init_Z_push', 0)
        self.localstore.update(handle, 'init_absE', False)
        self.localstore.update(handle, 'init_absXYZ', False)
        with open(filename) as f:
            for line in f:
                l = line.strip()
                self.process_line(handle, l, pfx="init_")
                ## This sleep is important since the io above is not actually
                ## blocking thus the plugin will not yield otherwise.
                await asyncio.sleep(0)
        await self.datastore.update(handle, "final_e", self.localstore.get(handle, 'init_E_push') + self.localstore.get(handle, 'init_E'))
        await self.datastore.update(handle, "final_z", self.localstore.get(handle, 'init_Z_push') + self.localstore.get(handle, 'init_Z'))

    def parseG(self, pattern, line):
        d = dict()
        for dim, val in pattern.findall(line):
            try:
                v = float(val)
            except ValueError:
                continue
            d[dim] = v
        return d

    async def done_cb(self, *args, **kwargs) -> None:
        device, = args
        handle = device.handle
        await self.datastore.update(handle, "stoptime", time())
        ## We only occationally (2Hz) write progress to the datastore as to
        ## not load the client/CNCD to much. So when we are done we might still
        ## have some information buffered, Flush that.
        accumulate = self.localstore.get(handle, 'accumulate')
        progress = self.datastore.get(handle, "progress")
        await self.datastore.update(handle, "progress", progress+accumulate)
        await self.datastore.update(handle, "current_z", self.localstore.get(handle, 'Z_push') + self.localstore.get(handle, 'Z'))
        await self.datastore.update(handle, "current_e", self.localstore.get(handle, 'E_push') + self.localstore.get(handle, 'E'))

    async def readline_cb(self, *args, **kwargs) -> None:
        device, line = args
        handle = device.handle
        now = time()
        ## Assuming each character takes up one byte add lenght of string
        ## to progress. Only every half a second write to datastore.
        self.localstore.inc(handle, 'accumulate', len(line))
        accumulate = self.localstore.get(handle, 'accumulate')

        self.process_line(handle, line.decode())

        if now - self.localstore.get(handle, 'last_update') > .5:
            self.localstore.update(handle, 'last_update', now)
            self.localstore.update(handle, 'accumulate', 0)
            progress = self.datastore.get(handle, "progress")
            await self.datastore.update(handle, "progress", progress+accumulate)
            await self.datastore.update(handle, "current_z", self.localstore.get(handle, 'Z_push') + self.localstore.get(handle, 'Z'))
            await self.datastore.update(handle, "current_e", self.localstore.get(handle, 'E_push') + self.localstore.get(handle, 'E'))


    ## Called when user/gui calls a command in HANDLES. Argv is this command
    ## followed by its arguments in the same style you know from sys.argv.
    ## for gcxt see __init__
    ## cctx - Connection context. Information about the connection with the
    ## user/gui. If you are careful you are allowed to store information here.
    ## lctx - Local context. Only lives during the handling of this command.
    ## use as you see fit.

    async def handle_command(self, gctx:dict, cctx:dict, lctx) -> None:
        argv = lctx.argv
        if len(argv) < 2:
            return "Must specify device"
        ## find device handle
        dev_id = argv[1]
        ## find all configured CNC devices (instances)
        cnc_devices = gctx['dev']
        if dev_id not in cnc_devices:
            return "Specified device not found"
        device = cnc_devices[dev_id]
        handle = device.handle
        progress = self.datastore.get(handle, "progress")
        total = self.datastore.get(handle, "filesize")
        msg = {"progress":progress, "total":total}
        lctx.write_json(msg)

    def help(self, cmd):
        if cmd == 'progress': #a plugin *might* have multiple handlers registered.
            return "'progress <DEVICE>' return file size in bytes and position in currently processed file."


    ## When CNCD restarts or exits the plugins get a change to properly close
    ## any resources they might hold.
    def close(self) -> None:
        pass


