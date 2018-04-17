import asyncio
import logging as log

def writeln(transport, msg):
    log.debug("Sending '{}'".format(msg))
    line = msg + '\n'
    transport.write(line.encode())

def last_resort(argv, ctx, transport):
    if argv[0] == '\x04': ## end of transmission
        log.debug("RX EOT. Closing my side of pipe")
        writelen(transport, "closing for you")
        transport.close()
        return
    writeln(transport, "UNHANDLED INPUT. HINT: type help")
    log.warning("UNHANDLED INPUT '{}'".format(argv))

async def sleep(argv, ctx, transport):
    log.info("sleeping")
    await asyncio.sleep(10)
    log.info("waking")

async def devices(argv, ctx, transport):
    """List configured devices"""
    devs = ctx['dev']
    writeln(transport, "Configured devices:")
    for dev in devs:
        writeln(transport, " {}".format(dev.cfg.name))

async def quit(argv, ctx, transport):
    """Disconnect this client."""
    writeln(transport, "closing for you")
    log.debug("Closing my side of pipe")
    transport.close()

async def terminate(argv, ctx, transport):
    """Exit at server side."""
    servers = ctx['srv']
    for server in servers:
        server.close()
    loop = asyncio.get_event_loop()
    loop.stop()

async def help(argv, ctx, transport):
    """Show this help."""
    global handlers
    writeln(transport, "COMMANDS:")
    for f in handlers:
        writeln(transport," {:<10}: {}".format(f.__name__, f.__doc__))


handlers = [sleep, quit, terminate, help, devices]
