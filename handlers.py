import functools
import asyncio
import logging as log
import os
import traceback
import time
from version import VERSION, API_VERSION

"""
gctx - Global context. No direct writes allowed. Exists during lifetime of program.
cctx - connection context. Think before writing. Multiple commands may exec parallel.
       Exist during lifetime of connection.
lctx - Local context. Write at will. Exist until command has been handled.
"""


## Some handydandy decorator doodads
def nargs(n):
    """ Only execute function when enough parameters are present"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(gctx, cctx, lctx):
            if len(lctx.argv) < n:
                return "Not enough arguments"
            return await func(gctx, cctx, lctx)
        return wrapper
    return decorator

def parse_device(func):
    """ Only execute function if first argument is resolvable to a configured
        device. Make sure to call @nargs first."""
    @functools.wraps(func)
    async def wrapper(gctx, cctx, lctx):
        devname = lctx.argv[1]
        configured_devices = gctx['dev']
        try:
            dev = configured_devices[devname]
        except KeyError:
            return "Device not found"
        return await func(gctx, cctx, lctx, dev)
    return wrapper

async def last_resort(gctx, cctx, lctx):
    if lctx.argv[0] == '\x04': ## end of transmission
        log.debug("RX EOT. Closing my side of pipe")
        cctx['transport'].close()
        return
    log.warning("UNHANDLED INPUT '{}'".format(lctx.argv))
    return "UNHANDLED INPUT. HINT: type help"

async def lsdir(dirname):
    try:
        objects = os.listdir(dirname)
    except FileNotFoundError:
        log.critical("Path doesn't exists")
        return []
    except PermissionError as e:
        log.error("No permission to list dir. {}".format(e))
        return []
    files = []
    for fn in objects:
        full = "{}/{}".format(dirname, fn)
        if os.path.isfile(full):
            files.append(full)
        elif os.path.isdir(full):
            files.extend(await lsdir(full))
        else:
            log.warning("not a file")
    return files

@nargs(2)
@parse_device
async def stat(gctx, cctx, lctx, dev):
    libpath = gctx['cfg'][dev.handle]['library']
    if libpath.endswith('/'):
        libpath = libpath[:-1]
    files = await lsdir(libpath)
    msg = {'files':files}
    lctx.write_json(msg)

async def hello(gctx, cctx, lctx):
    """version etc"""
    msg = {"cncd":VERSION, "api":API_VERSION, "time":time.time()}
    lctx.write_json(msg)

async def devlist(gctx, cctx, lctx):
    """List configured devices"""
    devs = gctx['dev']
    msg = {}
    for locator, device in devs.items():
        msg[locator] = device.get_name()
    lctx.write_json({'devices': msg})

async def camlist(gctx, cctx, lctx):
    """List configured webcams"""
    webcams = gctx['webcams']
    msg = {}
    for locator, webcam in webcams.items():
        msg[locator] = {'name':webcam.name, 'url':webcam.url}
    lctx.write_json({'webcams':msg})

async def dumpconfig(gctx, cctx, lctx):
    """List configuration file"""
    cfg = gctx['cfg']
    msg = {}
    for title, section in cfg.items():
        msg[title] = {}
        for key, value in section.items():
            msg[title][key] = value
    lctx.write_json(msg)

async def dumpgctx(gctx, cctx, lctx):
    """DEBUG List global context"""
    msg = {}
    for k,v in gctx.items():
        msg[str(k)] = str(v)
    lctx.write_json(msg)

async def dumpcctx(gctx, cctx, lctx):
    """DEBUG List connection context"""
    msg = {}
    for k,v in cctx.items():
        msg[str(k)] = str(v)
    lctx.write_json(msg)

async def dumplctx(gctx, cctx, lctx):
    """DEBUG List local context"""
    msg = {'lctx': str(lctx)}
    lctx.write_json(msg)

@nargs(2)
@parse_device
async def connect(gctx, cctx, lctx, dev):
    """Control configured devices"""
    if not await dev.connect():
        return "Connect failed"

@nargs(2)
@parse_device
async def disconnect(gctx, cctx, lctx, dev):
    """Control configured devices"""
    if not await dev.disconnect():
        return "Disconnect failed"

@nargs(3)
@parse_device
async def start(gctx, cctx, lctx, dev):
    """start executing gcode"""
    filename = lctx.argv[2]
    if not await dev.start(filename):
        return "Start failed"

@nargs(2)
@parse_device
async def abort(gctx, cctx, lctx, dev):
    """abort executing gcode, also works when device is blocked"""
    if not await dev.abort():
        return "Abort failed"

@nargs(2)
@parse_device
async def stop(gctx, cctx, lctx, dev):
    """stop executing gcode"""
    if not await dev.stop():
        return "stop failed"

@nargs(2)
@parse_device
async def pause(gctx, cctx, lctx, dev):
    """pause executing gcode"""
    if not await dev.pause():
        return "pause failed"

@nargs(2)
@parse_device
async def resume(gctx, cctx, lctx, dev):
    """resume executing gcode"""
    if not await dev.resume():
        return "resume failed"

async def quit(gctx, cctx, lctx):
    """Disconnect this client."""
    log.debug("Closing my side of pipe")
    cctx['transport'].close()

async def shutdown(gctx, cctx, lctx):
    """Exit at server side."""
    servers = gctx['srv']
    loop = gctx['loop']
    loop.stop()

async def reboot(gctx, cctx, lctx):
    """reboot server."""
    gctx['reboot'] = True
    await shutdown(gctx, cctx, lctx)

async def help(gctx, cctx, lctx):
    """Usage: 'help [COMMAND]'"""
    global handlers
    plugins = gctx["plugins"]

    if len(lctx.argv) > 1:
        msg = {}
        cmd = lctx.argv[1]
        for f in filter(lambda x: x.__name__==cmd, handlers):
            msg[f.__name__] = f.__doc__
        for plugin in plugins:
            for f in filter(lambda x: x==cmd, plugin.HANDLES):
                msg[f] = plugin.help(cmd)
    else:
        hdl = []
        for plugin in plugins:
            hdl.extend(plugin.HANDLES)
        commands = [f.__name__ for f in handlers]
        msg = {"builtin commands":commands, "plugin commands":hdl}
    lctx.write_json(msg)

async def loglevel(gctx, cctx, lctx):
    """Show or set log level"""
    rootlogger = log.getLogger()
    if len(lctx.argv) == 1:
        msg = {"Log level":log.getLevelName(rootlogger.getEffectiveLevel())}
        lctx.write_json(msg)
        return
    ## apply verbosity
    level = getattr(log, lctx.argv[1].upper(), None)
    if not isinstance(level, int):
        return "Log level needs to be one of: [DEBUG, INFO, WARNING, ERROR, CRITICAL]"
    rootlogger.setLevel(level)

handlers = [connect, disconnect, quit, shutdown, reboot, help, 
    devlist, camlist, loglevel, stat, hello,
    start, stop, abort, pause, resume, dumpconfig, dumpgctx, dumpcctx, dumplctx]
