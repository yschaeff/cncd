#!/usr/bin/env python3
from cfg import load_configuration
from collections import namedtuple
import logging as log
import asyncio, functools
import shlex ##shell lexer
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

def done_cb(gctx, cctx, lctx, future):
    try:
        r = future.result()
    except Exception as e:
        log.exception('Unexpected error')
        lctx.writeln("Server side exception: {}".format(str(e)))
        loop = asyncio.get_event_loop()
        loop.stop()
    lctx.writeln('.')

class TCP_handler(asyncio.Protocol):
    def __init__(self, ctx):
        self.gctx = ctx
        self.cctx = {}
        self.uid = 0
        log.debug("instantiating new connection")
    def connection_made(self, transport):
        self.cctx['transport'] = transport
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
            self.uid += 1
            argv = shlex.split(line)
            log.debug(argv)
            if not argv:
                continue
            try:
                nonce = int(argv[0])
                argv = argv[1:]
            except ValueError:
                nonce = self.uid
            cmd_handlers = [h for h in self.gctx['hdl'] if h.handles(argv)]
            # if we have multiple we must have an exact match
            exact = (len(cmd_handlers) != 1)
            cb = handlers.last_resort
            for handler in cmd_handlers:
                if not handler.handles(argv, exact): continue
                cb = handler.cb
                break
            ## we have a handler, construct a local context
            def writeln(msg):
                log.debug("Sending '{}'".format(msg))
                line = str(msg) + '\n'
                self.cctx['transport'].write("{} {}".format(nonce, line).encode())
            Lctx = namedtuple("Lctx", "nonce writeln argv")
            lctx = Lctx(nonce, writeln, argv)
            task = asyncio.ensure_future(cb(self.gctx, self.cctx, lctx))
            task.add_done_callback(functools.partial(done_cb, self.gctx, self.cctx, lctx))

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

    coro = loop.create_server(functools.partial(TCP_handler, CTX), general["address"], general["port"])
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
