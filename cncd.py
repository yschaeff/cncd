#!/usr/bin/env python3
from cfg import load_configuration
import logging as log
import asyncio

class Device():
    def __init__(self, dev_cfg):
        self.cfg = dev_cfg
        log.info("Added device \"{}\"".format(self.cfg.name))

@asyncio.coroutine
def handle_echo(reader, writer):
    global cfg
    addr = writer.get_extra_info('peername')
    log.info("New connection from {}".format(addr))
    data = yield from reader.read(100)
    message = data.decode()
    log.debug("Received %r from %r" % (message, addr))

    log.debug("Send: %r" % message)
    writer.write(data)
    yield from writer.drain()

    log.info("Close the client socket")
    writer.close()

# this will take care of config file, defaults commandline arguments and
# setting log levels
cfg = load_configuration()
general = cfg["general"]

dev_names = [name for name in cfg.sections() if name != "general"]
devs = [Device(cfg[name]) for name in dev_names]

loop = asyncio.get_event_loop()
coro = asyncio.start_server(handle_echo, general["address"], general["port"], loop=loop)
server = loop.run_until_complete(coro)
log.info('Serving on {}'.format(server.sockets[0].getsockname()))

try:
    loop.run_forever()
except KeyboardInterrupt:
    pass

server.close()
loop.run_until_complete(server.wait_closed())
## close existing connections
print(dir(coro))
asyncio.gather(*asyncio.Task.all_tasks()).cancel()
loop.stop()
loop.close()
