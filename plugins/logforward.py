import logging as log
from plugins.pluginskel import SkeletonPlugin
import os, asyncio
from time import time

class Plugin(SkeletonPlugin):

    PLUGIN_API_VERSION = 1
    NAME = "Log forwarder"
    PREHOOKS = {}
    POSTHOOKS = {}
    HANDLES = ['tracelog']

    async def handle_command(self, gctx:dict, cctx:dict, lctx) -> None:
        argv = lctx.argv
        if len(argv) < 2 or (argv[1] != 'start' and argv[1] != 'stop'):
            lctx.writeln("ERROR specify start or stop")
            return
        """args: start|stop receive server log messages"""
        class ByteStreamHandler(log.StreamHandler):
            def __init__(self, writefunc):
                super().__init__()
                self.writefunc = writefunc
            def emit(self, record):
                formatted = self.format(record)
                try:
                    self.writefunc(formatted)
                except:
                    ## never ever crash here. Trace might be logged!
                    pass
        if argv[1] == 'start':
            loghandler = ByteStreamHandler(lctx.writeln)
            formatter = log.Formatter('%(levelname)s:%(message)s')
            loghandler.setFormatter(formatter)
            rootlogger = log.getLogger()
            rootlogger.addHandler(loghandler)
            if 'tracelog_stop_event' not in cctx:
                event = asyncio.Event()
                event.clear()
                cctx['tracelog_stop_event'] = event
            else:
                event = cctx['tracelog_stop_event']
            event.clear()
            await event.wait()
            rootlogger.removeHandler(loghandler)
        else:
            if 'tracelog_stop_event' not in cctx:
                return
            event = cctx['tracelog_stop_event']
            event.set()


    ## When CNCD restarts or exits the plugins get a change to properly close
    ## any resources they might hold.
    async def close(self) -> None:
        pass

