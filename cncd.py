#!/usr/bin/env python3
from cfg import load_configuration
import logging as log
import asyncio
import shlex
import handlers

class Device():
    def __init__(self, dev_cfg):
        self.cfg = dev_cfg
        log.info("Added device \"{}\"".format(self.cfg.name))
    def connect(self):
        pass
    def load_file(self, filename):
        pass
    def start(self):
        pass
    def pause(self):
        pass
    def stop(self):
        pass

class Handler:
    def __init__(self, cb):
        self.cb = cb

    def handles(self, argv, exact=False):
        if exact:
            return argv[0] == self.cb.__name__
        return self.cb.__name__.startswith(argv[0])

    def handle(self, argv, ctx, transport):
        loop = asyncio.get_event_loop()
        loop.create_task(self.cb(argv, ctx, transport))
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
    def connection_lost(self, ex):
        log.debug("Connection closed")
    def eof_received(self):
        log.debug("Received EOF")
        return False

    def data_received(self, raw):
        try:
            data = raw.decode().strip()
        except UnicodeDecodeError:
            log.warning("I can't decode '{}' as unicode".format(raw))
            return
        lines = data.split('\n')
        for line in lines:
            argv = shlex.split(line)
            log.debug(argv)
            if not argv: continue
            cmd_handlers = [h for h in self.ctx['hdl'] if h.handles(argv)]
            # if we have multiple we must have an exact match
            exact = (len(cmd_handlers) != 1)
            for handler in cmd_handlers:
                if not handler.handles(argv, exact): continue
                handler.handle(argv, self.ctx, self.transport)
                break
            else:
                handlers.last_resort(argv, self.ctx, self.transport)

loop = asyncio.get_event_loop()
CTX = {}
while True:
    # this will take care of config file, defaults commandline arguments and
    # setting log levels
    CTX['cfg'] = load_configuration()
    CTX['dev'] = [Device(CTX['cfg'][name]) for name in CTX['cfg'].sections() if name != "general"]
    CTX['hdl'] = [Handler(name) for name in handlers.handlers]
    CTX['srv'] = []
    CTX['reboot'] = False

    general = CTX['cfg']["general"]

    coro = loop.create_server(lambda: TCP_handler(CTX), general["address"], general["port"])
    server = loop.run_until_complete(coro)
    CTX['srv'].append(server)

    log.info('Serving on {}'.format(server.sockets[0].getsockname()))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        log.info("Okay shutting down")
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        for server in CTX['srv']:
            ## TODO close current connections as well
            server.close()
        loop.run_until_complete(server.wait_closed())
    if not CTX['reboot']: break
loop.close()
