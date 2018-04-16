#!/usr/bin/env python3
from cfg import load_configuration
import logging as log
import asyncio
import shlex

class Device():
    def __init__(self, dev_cfg):
        self.cfg = dev_cfg
        log.info("Added device \"{}\"".format(self.cfg.name))

class Handler:
    def __init__(self, cb):
        self.cb = cb
    def handle(self, argv, ctx, transport):
        if argv[0] != self.cb.__name__:
            return False
        self.cb(argv, ctx, transport)
        return True

class TCP_handler(asyncio.Protocol):
    def __init__(self, ctx):
        self.ctx = ctx
        log.debug("instantiating new connection")
    def connection_made(self, transport):
        self.transport = transport
        peername = transport.get_extra_info('peername')
        log.info('Connection from {}'.format(peername))
        transport.write(">>> welcome\n".encode())

    def data_received(self, raw):
        data = raw.decode().strip()
        lines = data.split('\n')
        for line in lines:
            argv = shlex.split(line)
            log.debug(argv)
            if not argv: continue
            handlers = self.ctx['hdl']
            for handler in handlers:
                if handler.handle(argv, self.ctx, self.transport):
                    break
            else:
                log.warning("Unhandled input '{}'".format(line))
                self.transport.write("UNRECONIZED COMMAND. Try 'help'.\n".encode())

def quit(argv, ctx, transport):
    transport.write("closing for you\n".encode())
    transport.close()

def terminate(argv, ctx, transport):
    servers = ctx['srv']
    for server in servers:
        server.close()
    loop = asyncio.get_event_loop()
    loop.stop()

def help(argv, ctx, transport):
    transport.write("I don't know what to do!\n".encode())

# this will take care of config file, defaults commandline arguments and
# setting log levels
CTX = {}
CTX['cfg'] = load_configuration()
CTX['dev'] = [Device(cfg[name]) for name in CTX['cfg'].sections() if name != "general"]
CTX['hdl'] = []
CTX['hdl'].append( Handler(quit) )
CTX['hdl'].append( Handler(help) )
CTX['hdl'].append( Handler(terminate) )
CTX['srv'] = []
CTX['loop'] = None

general = CTX['cfg']["general"]

loop = asyncio.get_event_loop()
coro = loop.create_server(lambda: TCP_handler(CTX), general["address"], general["port"])
server = loop.run_until_complete(coro)
CTX['srv'].append(server)

log.info('Serving on {}'.format(server.sockets[0].getsockname()))
try:
    loop.run_forever()
except KeyboardInterrupt:
    pass

server.close()
loop.run_until_complete(server.wait_closed())
loop.close()
