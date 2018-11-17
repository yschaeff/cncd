#!/usr/bin/env python3
from cfg import load_configuration
from collections import namedtuple
import logging as log
import asyncio, functools, concurrent
import shlex ##shell lexer
import handlers, serial
import serial_asyncio
import os

class Device():
    def __init__(self, dev_cfg):
        self.cfg = dev_cfg
        self.con = None
        log.info("Added device \"{}\"".format(self.cfg.name))
        log.debug(dir(dev_cfg))
        self.connected = False
        self.gcodefile = None
    def status(self):
        s = "connected {}".format(self.connected)
        return s
    def send_gcode(self, gcode):
        if not self.con:
            log.error("not connected")
            return False
        self.con.write(gcode.encode())
        self.con.write('\n'.encode())
        l = self.con.read(1)
        log.debug(l)
        return True

    def connect(self):
        def done_cb(future):
            try:
                r = future.result()
            except concurrent.futures._base.CancelledError:
                log.warning('Task preemtively cancelled')
            except FileNotFoundError as e:
                print("ERROR {}".format(str(e)))
            except serial.serialutil.SerialException as e:
                log.critical("ERROR {}".format(str(e)))
            except Exception as e:
                print("ERROR Server side exception: {}".format(str(e)))
            else:
                print("AIGHT")

        class SerialHandler(asyncio.Protocol):
            #def __init__(self, A 3D PRINTER!
            def connection_made(self, transport):
                self.transport = transport
                log.info("Serial port {} opened".format(transport.serial.name))
                log.debug('Serial properties: {}'.format(transport))
                #transport.write(b'Hello, World!\n')  # Write serial data via transport

            def data_received(self, data):
                print('data received', repr(data))
                #if b'\n' in data:
                    #self.transport.close()

            def connection_lost(self, exc):
                print('port closed')
                self.transport.loop.stop()

            def pause_writing(self):
                print('pause writing')
                print(self.transport.get_write_buffer_size())

            def resume_writing(self):
                print(self.transport.get_write_buffer_size())
                print('resume writing')

        loop = asyncio.get_event_loop()
        coro = serial_asyncio.create_serial_connection(loop, SerialHandler,
                self.cfg["port"], baudrate=self.cfg["baud"])
        task = asyncio.ensure_future(coro)
        task.add_done_callback(done_cb)
        return True
    def disconnect(self):
        if self.con:
            self.con.close()
            self.con = None
        return True
    def load_file(self, filename):
        self.gcodefile = filename
        return True
    def start(self): ## rename print file?
        if not self.gcodefile: return False ## emit warning
        if not self.con: return False

        ## first read all the lines in the buffer
        while self.con.in_waiting:
            rx = self.con.readline()
            log.info("PRINTER: {}".format(rx.decode()))

        with open(self.gcodefile) as fd:
            for line in fd:
                idx = line.rfind(';')
                if idx>=0: line = line[:idx]
                gcode = line.strip() + '\n'
                print(gcode)
                self.con.write(gcode.encode())
                ## wait for response
                rx = self.con.readline()
                log.info("PRINTER: {}".format(rx.decode()))

                #l = self.con.read(1)
                #l = self.con.readline()
                #log.debug(l)
                #import time
                #time.sleep(2)
                #while self.con.in_waiting:
                    #rx = self.con.readline()
                    #log.info("PRINTER: {}".format(rx.decode()))
        return True
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
        CTX['dev'][name] = Device(CTX['cfg'][name])


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
