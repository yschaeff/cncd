#!/usr/bin/env python3
from collections import namedtuple
import logging as log
import asyncio, functools, concurrent, json
import shlex ##shell lexer
import serial_asyncio
import os, socket, traceback
import handlers, robot, serial
from pluginmanager import PluginManager
from cfg import load_configuration
from datastore import DataStore

CLEAN_EXIT = True

class Handler:
    def __init__(self, name, cb):
        self.cb = cb
        self.name = name

    def handles(self, argv, exact=False):
        if exact:
            return argv[0] == self.name
        return self.name.startswith(argv[0])

def done_cb(gctx, cctx, lctx, future):
    global CLEAN_EXIT
    try:
        r = future.result()
    except concurrent.futures._base.CancelledError:
        r = 'Task preemptively cancelled'
    except Exception as e:
        log.exception('Unexpected error')
        print(traceback.format_exc())
        r = "Server side exception: {}".format(str(e))

    if r is not None:
        msg = {'ERROR':r}
        lctx.write_json(msg)
    lctx.writeln('.')

def command(line, gctx, cctx={'uid':0}, loopback=False):
    cctx['uid'] += 1
    try:
        argv = shlex.split(line)
    except ValueError as e:
        nonce = cctx['uid']
        cctx['transport'].write("{} {}\n{} .\n".format(nonce, json.dumps({'ERROR':"Could not parse."}), nonce).encode())
        return False
    log.debug(argv)
    if not argv: return True
    try:
        nonce = int(argv[0])
        argv = argv[1:]
    except ValueError:
        nonce = cctx['uid']
    if not argv: return True
    cmd_handlers = [h for h in gctx['hdl'] if h.handles(argv)]
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
        if loopback: return
        ## This function might be called by a log handler.
        ## do not emit any log messages in this func!
        line = str(msg) + '\n'
        transport = cctx['transport']
        if transport.is_closing():
            ## an exception here would cause a log message to be emitted!
            ## so don't attempt to write!
            return
        transport.write("{} {}".format(nonce, line).encode())
    def write_json(msg):
        ## ONLY ENABLE THIS AS LAST RESORT. WILL CAUSE LOOPS! ##
        ##            log.debug(json.dumps(msg))              ##
        return writeln(json.dumps(msg))
    Lctx = namedtuple("Lctx", "nonce writeln argv write_json")
    lctx = Lctx(nonce, writeln, argv, write_json)
    task = asyncio.ensure_future(cb(gctx, cctx, lctx))
    task.add_done_callback(functools.partial(done_cb, gctx, cctx, lctx))
    return True

class SocketHandler(asyncio.Protocol):
    def __init__(self, gctx):
        super().__init__()
        self.gctx = gctx
        self.cctx = {'uid':0}
        log.debug("instantiating new connection")
        self.data = ""
    def connection_made(self, transport):
        self.cctx['transport'] = transport
        prop = ['peername','sockname'][transport.get_extra_info('socket').family == socket.AF_UNIX]
        src = transport.get_extra_info(prop)
        log.info('Connection from {}'.format(src))
        transport.write("## CNCD\n".encode())
    def connection_lost(self, ex):
        log.info('Closed connection')
    def eof_received(self):
        log.debug("Received EOF")
        return False

    def prepare_command(self, line):
        if not command(line, self.gctx, self.cctx, loopback=False):
            log.info("Failed to parse '{}'".format(line))

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
            self.prepare_command(line)

def load_devices_from_cfg(gctx):
    cfg = gctx['cfg']
    general = cfg["general"]

    ## Do not delete devices. otherwise we can't control existing devices!
    #gctx['dev'] = {}
    cnc_devices = [dev.strip() for dev in general['cnc_devices'].split(',')]
    for device in cnc_devices:
        try:
            section = cfg[device]
        except KeyError:
            log.error("Can not find section {} in configuration.".format(device))
            continue
        if device in gctx['dev']:
            gctx['dev'][device].update_cfg(section)
        else:
            gctx['dev'][device] = robot.Device(device, section, gctx)

def load_webcams_from_cfg(gctx):
    cfg = gctx['cfg']
    general = cfg["general"]

    gctx['webcams'] = {}
    Webcam = namedtuple("Webcam", "name url")
    cameras = [cam.strip() for cam in general['cameras'].split(',')]
    for camera in cameras:
        try:
            section = cfg[camera]
            gctx['webcams'][camera] = Webcam(section['name'], section['url'])
        except KeyError:
            log.error("Error in section {} of configuration.".format(camera))
            continue

def load_plugins_from_cfg(gctx):
    pluginmanager = PluginManager(gctx)
    gctx['pluginmanager'] = pluginmanager
    pluginmanager.load_plugins()
    gctx['hdl'] += [Handler(handle, callback) for handle, callback in pluginmanager.get_handlers()]

if __name__ == '__main__':
    if not os.geteuid():
        log.fatal('Thou Shalt Not Run As Root.')
        exit(1)

    loop = asyncio.get_event_loop()
    gctx = {}
    gctx['dev'] = {}
    gctx['loop'] = loop
    while True:
        # this will take care of config file, defaults commandline arguments and
        # setting log levels
        cfg = load_configuration()
        
        gctx['cfg'] = cfg
        gctx['hdl'] = [Handler(callback.__name__, callback) for callback in handlers.handlers]
        gctx['srv'] = []
        gctx['reboot'] = False
        gctx['datastore'] = DataStore()

        general = cfg["general"]

        load_devices_from_cfg(gctx)
        load_webcams_from_cfg(gctx)
        load_plugins_from_cfg(gctx)

        ##TCP
        if "address" in general and "port" in general:
            log.critical("Gee Skipper! It looks like you are trying to open a TCP port! This is highly discouraged, for TCP provides no access control. Even opening on localhost exposes your devices to non privileged users on this system. Don't say I didn't told you so!")
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
            gctx['srv'].append(server)
            log.info('Serving on {}'.format(server.sockets[0].getsockname()))
        except FileNotFoundError:
            log.error("Socket file {} not accessible.".format(general["unix_socket"]))

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
        gctx['pluginmanager'].unload_plugins()
        if not gctx['reboot']: break

    pending = asyncio.Task.all_tasks()
    for task in pending: task.cancel()
    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

    loop.close()
    if not CLEAN_EXIT:
        exit(1)
