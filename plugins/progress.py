import logging as log
from plugins.pluginskel import SkeletonPlugin
import os
from time import time
from collections import defaultdict

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
        ## This plugin keeps some internal administration:
        self.last_update = defaultdict(int)
        self.accumulate = defaultdict(int)

    ## Specifically defined for this plugin. However the function signature is
    ## important. The function MUST be defined async. Because CNCD is single
    ## threaded it is super important to NOT DO ANY LONG OPERATIONS here. If
    ## you ABSOLUTELY must then occasionally "await asyncio.sleep(0)" to handle
    ## control back to the scheduler for a bit.
    ## Make sure the function signature is compatible with the function hooked.
    async def open_cb(self, *args, **kwargs) -> None:
        device, filename = args
        handle = device.handle
        ## For the datastore the convention is to store all device specific
        ## information with device.handle as key. System wide should
        ## use 'general'
        await self.datastore.update(handle, "starttime", time())
        await self.datastore.update(handle, "stoptime", -1)
        await self.datastore.update(handle, "filename", filename)
        await self.datastore.update(handle, "filesize", os.path.getsize(filename))
        await self.datastore.update(handle, "progress", 0)
        self.accumulate[handle] = 0

    async def done_cb(self, *args, **kwargs) -> None:
        device, = args
        handle = device.handle
        await self.datastore.update(handle, "stoptime", time())
        ## We only occationally (2Hz) write progress to the datastore as to
        ## not load the client/CNCD to much. So when we are done we might still
        ## have some information buffered, Flush that.
        accumulate = self.accumulate[handle]
        progress = self.datastore.get(handle, "progress")
        await self.datastore.update(handle, "progress", progress+accumulate)

    async def readline_cb(self, *args, **kwargs) -> None:
        device, line = args
        handle = device.handle
        now = time()
        ## Assuming each character takes up one byte add lenght of string
        ## to progress. Only every half a second write to datastore.
        self.accumulate[handle] += len(line)
        if now - self.last_update[handle] > .5:
            self.last_update[handle] = now
            accumulate = self.accumulate[handle]
            self.accumulate[handle] = 0
            progress = self.datastore.get(handle, "progress")
            await self.datastore.update(handle, "progress", progress+accumulate)


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
            lctx.writeln("ERROR Must specify device")
            return
        ## find device handle
        dev_id = argv[1]
        ## find all configured CNC devices (instances)
        cnc_devices = gctx['dev']
        if dev_id not in cnc_devices:
            lctx.writeln("ERROR Specified device not found")
            return
        device = cnc_devices[dev_id]
        handle = device.handle
        progress = self.datastore.get(handle, "progress")
        total = self.datastore.get(handle, "filesize")
        lctx.writeln("{} / {}".format(progress, total))


    ## When CNCD restarts or exits the plugins get a change to properly close
    ## any resources they might hold.
    def close(self) -> None:
        pass


