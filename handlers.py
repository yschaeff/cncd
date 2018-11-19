import functools
import asyncio
import logging as log
import os

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
                lctx.writeln("ERROR Not enough arguments")
                return
            await func(gctx, cctx, lctx)
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
            lctx.writeln("ERROR Device not found")
            return
        await func(gctx, cctx, lctx, dev)
    return wrapper


async def last_resort(gctx, cctx, lctx):
    if lctx.argv[0] == '\x04': ## end of transmission
        log.debug("RX EOT. Closing my side of pipe")
        lctx.writeln("closing for you")
        cctx['transport'].close()
        return
    lctx.writeln("UNHANDLED INPUT. HINT: type help")
    log.warning("UNHANDLED INPUT '{}'".format(lctx.argv))

@nargs(2)
async def sleep(gctx, cctx, lctx):
    """Test async functionality"""
    try:
        t = int(lctx.argv[1])
    except ValueError:
        t = 0
    lctx.writeln("sleeping for {} seconds".format(t))
    await asyncio.sleep(t)
    lctx.writeln("waking")

async def lsdir(dirname):
    try:
        objects = os.listdir(dirname)
    except FileNotFoundError:
        log.critical("Path doesn't exists")
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

async def stat(gctx, cctx, lctx):
    libpath = gctx['cfg']['general']['library']
    files = await lsdir(libpath)
    for f in files:
        lctx.writeln(f)

async def devlist(gctx, cctx, lctx):
    """List configured devices"""
    devs = gctx['dev']
    for name in devs.keys():
        lctx.writeln("{}".format(name))

async def dumpconfig(gctx, cctx, lctx):
    """List configuration file"""
    cfg = gctx['cfg']
    for title, section in cfg.items():
        lctx.writeln("[{}]".format(title))
        for key, value in section.items():
            lctx.writeln("{} = {}".format(key, value))
        lctx.writeln("")

async def dumpgctx(gctx, cctx, lctx):
    """DEBUG List global context"""
    for k,v in gctx.items():
        lctx.writeln("{}: {}".format(k, v))

async def dumpcctx(gctx, cctx, lctx):
    """DEBUG List connection context"""
    for k,v in cctx.items():
        lctx.writeln("{}: {}".format(k, v))

async def dumplctx(gctx, cctx, lctx):
    """DEBUG List local context"""
    lctx.writeln("{}".format(lctx))

@nargs(2)
@parse_device
async def connect(gctx, cctx, lctx, dev):
    """Control configured devices"""
    if await dev.connect():
        lctx.writeln("OK")
    else:
        lctx.writeln("ERROR")

@nargs(2)
@parse_device
async def disconnect(gctx, cctx, lctx, dev):
    """Control configured devices"""
    if dev.disconnect():
        lctx.writeln("OK")
    else:
        lctx.writeln("ERROR")

@nargs(2)
@parse_device
async def status(gctx, cctx, lctx, dev):
    """Control configured devices"""
    status = dev.status()
    lctx.writeln(status)

@nargs(3)
@parse_device
async def load(gctx, cctx, lctx, dev):
    """Assign gcode file to printer"""
    argv = lctx.argv
    filename = argv[2]
    if dev.load_file(filename):
        lctx.writeln("OK")
    else:
        lctx.writeln("ERROR")

@nargs(2)
@parse_device
async def start(gctx, cctx, lctx, dev):
    """start executing gcode"""
    if await dev.start():
        lctx.writeln("OK")
    else:
        lctx.writeln("ERROR")

@nargs(3)
@parse_device
async def gcode(gctx, cctx, lctx, dev):
    """List configured devices"""
    argv = lctx.argv
    gcode = argv[2]
    if dev.send_gcode(gcode):
        lctx.writeln("OK")
    else:
        lctx.writeln("ERROR Device not connected?")

async def quit(gctx, cctx, lctx):
    """Disconnect this client."""
    lctx.writeln("closing for you")
    log.debug("Closing my side of pipe")
    cctx['transport'].close()

async def shutdown(gctx, cctx, lctx):
    """Exit at server side."""
    servers = gctx['srv']
    loop = asyncio.get_event_loop()
    loop.stop()

async def reboot(gctx, cctx, lctx):
    """reboot server."""
    gctx['reboot'] = True
    await shutdown(gctx, cctx, lctx)

async def help(gctx, cctx, lctx):
    """Show this help."""
    global handlers
    lctx.writeln("COMMANDS:")
    for f in handlers:
        lctx.writeln(" {:<10}: {}".format(f.__name__, f.__doc__))

async def loglevel(gctx, cctx, lctx):
    """Show or set log level"""
    rootlogger = log.getLogger()
    if len(lctx.argv) == 1:
        lctx.writeln("Log level: {}".format(log.getLevelName(rootlogger.getEffectiveLevel())))
        return
    ## apply verbosity
    level = getattr(log, lctx.argv[1].upper(), None)
    if not isinstance(level, int):
        lctx.writeln("Log level needs to be one of: [DEBUG, INFO, WARNING, ERROR, CRITICAL]")
        return
    rootlogger.setLevel(level)

handlers = [connect, disconnect, status, load, quit, shutdown, reboot, help, 
    devlist, loglevel, stat, gcode,
    start, dumpconfig, dumpgctx, dumpcctx, dumplctx, sleep]
