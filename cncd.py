#!/usr/bin/env python3
from cfg import load_configuration
from collections import namedtuple
import logging as log
import asyncio, functools, concurrent
import shlex ##shell lexer
import handlers, robot, serial
import serial_asyncio
import os

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
    except concurrent.futures._base.CancelledError:
        lctx.writeln('Task preemtively cancelled')
    except Exception as e:
        log.exception('Unexpected error')
        lctx.writeln("ERROR Server side exception: {}".format(str(e)))
        loop = asyncio.get_event_loop()
        loop.stop()
    lctx.writeln('.')

class SocketHandler(asyncio.Protocol):
    def __init__(self, ctx):
        super().__init__()
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
        log.info('Closed connection')
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
            for handler in cmd_handlers:
                if not handler.handles(argv, exact): continue
                cb = handler.cb
                break
            else:
                cb = handlers.last_resort
            ## we have a handler, construct a local context
            def writeln(msg):
                log.debug("Sending '{}'".format(msg))
                line = str(msg) + '\n'
                self.cctx['transport'].write("{} {}".format(nonce, line).encode())
            Lctx = namedtuple("Lctx", "nonce writeln argv")
            lctx = Lctx(nonce, writeln, argv)
            log.debug("gctx {} cctx {} lctx {}".format(self.gctx, self.cctx, lctx))
            task = asyncio.ensure_future(cb(self.gctx, self.cctx, lctx))
            task.add_done_callback(functools.partial(done_cb, self.gctx, self.cctx, lctx))

if not os.geteuid():
    log.fatal('Thou Shalt Not Run As Root.')
    exit(1)

loop = asyncio.get_event_loop()
CTX = {}
while True:
    # this will take care of config file, defaults commandline arguments and
    # setting log levels
    CTX['cfg'] = load_configuration()
    CTX['hdl'] = [Handler(name) for name in handlers.handlers]
    CTX['srv'] = []
    CTX['reboot'] = False
    CTX['dev'] = {}
    for name in CTX['cfg'].sections():
        if name == "general": continue
        CTX['dev'][name] = robot.Device(CTX['cfg'][name])

    general = CTX['cfg']["general"]

    ##TCP
    coro = loop.create_server(functools.partial(SocketHandler, CTX),
            general["address"], general["port"])
    server = loop.run_until_complete(coro)
    CTX['srv'].append(server)
    log.info('Serving on {}'.format(server.sockets[0].getsockname()))

    ##UNIX
    coro = loop.create_unix_server(functools.partial(SocketHandler, CTX),
            path=general["unix_socket"])
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
            log.debug("shutting down service")
            server.close()
            loop.run_until_complete(server.wait_closed())
    if not CTX['reboot']: break

pending = asyncio.Task.all_tasks()
for task in pending: task.cancel()
loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

loop.close()
