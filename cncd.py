#!/usr/bin/env python3
from cfg import load_configuration
from collections import namedtuple
import logging as log
import asyncio, functools, concurrent
import shlex ##shell lexer
import handlers, robot, serial
from pluginmanager import PluginManager
import serial_asyncio
import os, socket, traceback

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
    def __init__(self, gctx):
        super().__init__()
        self.gctx = gctx
        self.cctx = {}
        self.uid = 0
        log.debug("instantiating new connection")
        self.data = ""
    def connection_made(self, transport):
        self.cctx['transport'] = transport
        prop = ['peername','sockname'][transport.get_extra_info('socket').family == socket.AF_UNIX]
        src = transport.get_extra_info(prop)
        log.info('Connection from {}'.format(src))
        transport.write(">>> welcome\n".encode())
    def connection_lost(self, ex):
        log.info('Closed connection')
    def eof_received(self):
        log.debug("Received EOF")
        return False

    def command(self, line):
        self.uid += 1
        try:
            argv = shlex.split(line)
        except ValueError:
            self.cctx['transport'].write("You talk nonsense! HUP!\n".encode())
            self.cctx['transport'].close()
            return
        log.debug(argv)
        if not argv:
            return
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
        task = asyncio.ensure_future(cb(self.gctx, self.cctx, lctx))
        task.add_done_callback(functools.partial(done_cb, self.gctx, self.cctx, lctx))

    def data_received(self, raw):
        try:
            self.data += raw.decode()
        except UnicodeDecodeError:
            log.warning("I can't decode '{}' as unicode".format(raw))
            self.data = ""
            return
        while True:
            idx = self.data.find('\n')
            if idx < 0: break
            line = self.data[:idx+1]
            self.data = self.data[idx+1:]
            self.command(line)

if not os.geteuid():
    log.fatal('Thou Shalt Not Run As Root.')
    exit(1)

loop = asyncio.get_event_loop()
gctx = {}
while True:
    # this will take care of config file, defaults commandline arguments and
    # setting log levels
    cfg = load_configuration()
    
    gctx['cfg'] = cfg
    gctx['hdl'] = [Handler(name) for name in handlers.handlers]
    gctx['srv'] = []
    gctx['reboot'] = False

    general = cfg["general"]

    ## gather all CNC devices
    gctx['dev'] = {}
    cnc_devices = [dev.strip() for dev in general['cnc_devices'].split(',')]
    for device in cnc_devices:
        try:
            section = cfg[device]
        except KeyError:
            log.error(f"Can not find section {device} in configuration.")
            continue
        gctx['dev'][device] = robot.Device(section, gctx)

    pluginmanager = PluginManager(gctx)
    gctx['pluginmanager'] = pluginmanager
    pluginmanager.load_plugins()

    ##TCP
    coro = loop.create_server(functools.partial(SocketHandler, gctx),
            general["address"], general["port"])
    server = loop.run_until_complete(coro)
    gctx['srv'].append(server)
    log.info('Serving on {}'.format(server.sockets[0].getsockname()))

    ##UNIX
    coro = loop.create_unix_server(functools.partial(SocketHandler, gctx),
            path=general["unix_socket"])
    try:
        server = loop.run_until_complete(coro)
    except FileNotFoundError:
        log.error("Socket file {} not accessible.".format(general["unix_socket"]))
    gctx['srv'].append(server)
    log.info('Serving on {}'.format(server.sockets[0].getsockname()))

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        log.info("Okay shutting down")
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        for server in gctx['srv']:
            ## TODO close current connections as well
            log.debug("shutting down service")
            server.close()
            loop.run_until_complete(server.wait_closed())
    pluginmanager.unload_plugins()
    if not gctx['reboot']: break

pending = asyncio.Task.all_tasks()
for task in pending: task.cancel()
loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

loop.close()
