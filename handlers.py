import asyncio
import logging as log

async def sleep(argv, ctx, transport):
    log.info("sleeping")
    await asyncio.sleep(10)
    log.info("waking")

def last_resort(argv, ctx, transport):
    if argv[0] == '\x04': ## end of transmission
        log.debug("RX EOT. Closing my side of pipe")
        transport.write("closing for you\n".encode())
        transport.close()
        return
    transport.write("UNHANDLED INPUT\n".encode())
    log.warning("UNHANDLED INPUT '{}'".format(argv))

async def quit(argv, ctx, transport):
    transport.write("closing for you\n".encode())
    log.debug("Closing my side of pipe")
    transport.close()

async def terminate(argv, ctx, transport):
    servers = ctx['srv']
    for server in servers:
        server.close()
    loop = asyncio.get_event_loop()
    loop.stop()

async def help(argv, ctx, transport):
    transport.write("I don't know what to do!\n".encode())


handlers = [sleep, quit, terminate, help]
