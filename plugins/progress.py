import logging as log
from plugins.pluginskel import SkeletonPlugin
import os
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
    def __init__(self, gctx:dict):
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
        }
        ## The rest is specific to this plugin
        self.gctx = gctx
        class Progress:
            def __init__(self):
                self.progress = 0
                self.total = 0
            def __repr__(self):
                return "{}/{}".format(self.progress, self.total)
        self.devices = defaultdict(Progress)


    ## Specifically defined for this plugin. However the function signature is
    ## important. The function MUST be defined async. Because CNCD is single
    ## threaded it is super important to NOT DO ANY LONG OPERATIONS here. If
    ## you ABSOLUTELY must then occasionally "await asyncio.sleep(0)" to handle
    ## control back to the scheduler for a bit.
    async def open_cb(self, *args, **kwargs) -> None:
        device, filename = args
        self.devices[device].total = os.path.getsize(filename)

    async def readline_cb(self, *args, **kwargs) -> None:
        device, line = args
        self.devices[device].progress += len(line)


    ## Called when user/gui calls a command in HANDLES. Argv is this command
    ## followed by its arguments in the same style you know from sys.argv.
    ## for gcxt see __init__
    ## cctx - Connection context. Information about the connection with the
    ## user/gui. If you are careful you are allowed to store information here.
    ## lctx - Local context. Only lives during the handling of this command.
    ## use as you see fit.
    ##
    ## This function should be a generator (so the caller can read line by line
    ## and handle any multitasking) and thus should return None (StopIteration).
    ## It yields strings which are meant to be parsed by the caller.
    def handle_command(self, argv:list, gctx:dict, cctx:dict, lctx) -> None:
        if len(argv) < 2:
            yield "ERROR Must specify device"
            return
        ## find device handle
        dev_id = argv[1]
        ## find all configured CNC devices (instances)
        cnc_devices = gctx['dev']
        if dev_id not in cnc_devices:
            yield "ERROR Specified device not found"
            return
        device = cnc_devices[dev_id]
        ## find progress for the queried device
        progress = self.devices[device]
        yield str(progress)


    ## When CNCD restarts or exits the plugins get a change to properly close
    ## any resources they might hold.
    def close(self) -> None:
        pass


