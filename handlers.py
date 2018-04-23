import asyncio
import logging as log
import os

async def last_resort(gctx, lctx):
    if lctx.argv[0] == '\x04': ## end of transmission
        log.debug("RX EOT. Closing my side of pipe")
        lctx.writeln("closing for you")
        lctx.transport.close()
        return
    lctx.writeln("UNHANDLED INPUT. HINT: type help")
    log.warning("UNHANDLED INPUT '{}'".format(lctx.argv))

async def sleep(gctx, lctx):
    log.info("sleeping")
    await asyncio.sleep(10)
    log.info("waking")

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

async def stat(gctx, lctx):
    libpath = gctx['cfg']['general']['library']
    files = await lsdir(libpath)
    lctx.writeln(files)

async def dev(gctx, lctx):
    """List configured devices"""
    devs = gctx['dev']
    lctx.writeln("Configured devices:")
    for i, dev in enumerate(devs):
        lctx.writeln(" {} - {}".format(i, dev.cfg.name))

async def quit(gctx, lctx):
    """Disconnect this client."""
    lctx.writeln("closing for you")
    log.debug("Closing my side of pipe")
    lctx.transport.close()

async def shutdown(gctx, lctx):
    """Exit at server side."""
    servers = gctx['srv']
    for server in servers:
        server.close()
    loop = asyncio.get_event_loop()
    loop.stop()

async def reboot(gctx, lctx):
    """reboot server."""
    gctx['reboot'] = True
    await shutdown(gctx, lctx)

async def help(gctx, lctx):
    """Show this help."""
    global handlers
    lctx.writeln("COMMANDS:")
    for f in handlers:
        lctx.writeln(" {:<10}: {}".format(f.__name__, f.__doc__))

async def loglevel(gctx, lctx):
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

handlers = [sleep, quit, shutdown, reboot, help, dev, loglevel, stat]
