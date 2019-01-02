import logging as log
import asyncio, functools, concurrent
import serial
import serial_asyncio
import os, re

from pluginmanager import plugin_hook
import flavour

class DummySerialConnection():
    def __init__(self, device):
        self.device = device
        device.handler = self
    def close(self):
        self.device.handler = None
        log.info("Dummy serial connection closed")
    def write(self, msg):
        async def slow_ack():
            await asyncio.sleep(.01)
            await self.device.rx(b'ok\n')
        task = asyncio.ensure_future(slow_ack())

class CncConnection(asyncio.Protocol):
    """Implements protocol"""
    def __init__(self, device):
        self.device = device
        device.handler = self
        self.expect_close = False
        super().__init__()
    def connection_made(self, transport):
        self.transport = transport
    def data_received(self, data):
        task = asyncio.ensure_future(self.device.rx(data))
    def connection_lost(self, exc):
        if not self.expect_close:
            log.error('Device vanished!')
        else:
            log.info('Connection closed')
        self.device.handler = None
    def close(self):
        self.transport.close()
    def write(self, msg):
        self.transport.write(msg)

class Device():
    """General CNC device, keeps state, buffers etc"""
    def __init__(self, handle, dev_cfg, gctx):
        self.cfg = dev_cfg
        self.gctx = gctx
        self.handle = handle
        self.con = None
        log.info("Added device \"{}\"".format(self.cfg['name']))
        self.connected = False
        self.gcodefile = None
        self.handler = None
        self.input_buffer = b''
        self.gcode_task = None
        self.is_printing = False
        self.resent = False
        self.sendlock = asyncio.Lock()
        self.stop_event = asyncio.Event()
        self.resume_event = asyncio.Event()
        self.response_event = asyncio.Event()
        self.resume_event.set() ## start not paused
        self.gctx['datastore'].update_nocoro(self.handle, 'paused', False)
        self.gctx['datastore'].update_nocoro(self.handle, 'idle', True)
        self.gctx['datastore'].update_nocoro(self.handle, 'selected', "")
        self.firmware = flavour.get_firmware(dev_cfg.get("firmware", "generic"))

    async def store(self, key, value):
        await self.gctx['datastore'].update(self.handle, key, value)

    def update_cfg(self, dev_cfg):
        self.cfg = dev_cfg

    def get_name(self):
        return self.cfg['name']

    @plugin_hook
    async def incoming(self, response):
        ## sanitized response
        return response

    def sanitize_response(self, response):
        r = response.decode().strip()
        ## A telnet based printer might send us a prompt
        if r[0] == '>':
            r = r[1:]
        return r.strip() ##

    async def rx(self, data):
        self.input_buffer += data
        while True:
            index = self.input_buffer.find(b'\n')
            if index < 0: break
            line = self.input_buffer[:index+1]
            self.input_buffer = self.input_buffer[index+1:]
            response = await self.incoming(self.sanitize_response(line))
            log.debug("response {}: '{}'".format(self.cfg['name'], response))
            ## TODO zmorph sends no ok on rs!
            if response.startswith('ok'):
                self.response_event.set()
            elif response.startswith('rs') or response.startswith('Resend'):
                ## TODO: parse linenumber and log big fat critical if!=lastline
                self.resent = True
                #if !prusa:
                    #self.response_event.set()
                self.response_event.set()
            else:
                log.info('Device "{}" responded with "{}"'.format(self.handle, response))

    def status(self):
        c = (self.handler != None)
        p = self.is_printing
        fstaged = self.gcodefile
        paused = not self.resume_event.is_set()

        s  =  "connected:{}".format(c)
        s += " printing:{}".format(p)
        s += " staged:\"{}\"".format(fstaged)
        s += " paused:{}".format(paused)
        return s

    @plugin_hook
    async def connect(self):
        ## create serial server:
        def done_cb(event, device, future):
            try:
                r = future.result()
            except concurrent.futures._base.CancelledError:
                log.warning('Connect task cancelled')
            except FileNotFoundError as e:
                log.error(str(e))
            except serial.serialutil.SerialException as e:
                log.error(str(e))
            except Exception as e:
                log.critical(str(e))
            else:
                device.success = True
            finally:
                event.set()
        if self.handler:
            log.warning("Requested connect. But already connected.")
            return True
        event = asyncio.Event()
        self.response_event = asyncio.Event()
        self.forceful_stop = False
        self.success = False
        self.linenumber = 0
        loop = self.gctx['loop']

        port_spec = re.compile("^(.+)://(.+)[@:]([0-9]+)$")
        port = self.cfg["port"].strip()
        if not port_spec.match(port):
            log.error("port property in configuration not parsable.")
            return False
        ## the result must have three groups exactly"
        proto, addr, param = port_spec.findall(port)[0] ## we can only have one
        if proto == 'dummy':
            DummySerialConnection(self)
            self.success = True
        elif proto == 'serial':
            coro = serial_asyncio.create_serial_connection(loop,
                functools.partial(CncConnection, self), addr, baudrate=param)
            task = asyncio.ensure_future(coro)
            task.add_done_callback(functools.partial(done_cb, event, self))
            await event.wait()
        elif proto == 'tcp':
            coro = loop.create_connection(functools.partial(CncConnection, self), addr, param)
            task = asyncio.ensure_future(coro)
            task.add_done_callback(functools.partial(done_cb, event, self))
            await event.wait()

        if self.success:
            log.info("Device connected successfully.")
            self.input_buffer = b''
            await self.gctx['datastore'].update(self.handle, 'connected', True)
        else:
            log.error("Unable to connect to device.")
        ## this needs to be a callback on success?
        #await self.send("N0 M110", wait_for_ack=False)
        return self.success

    @plugin_hook
    async def disconnect(self):
        if self.handler:
            await self.resume()
            self.handler.expect_close = True
            self.handler.close()
            self.response_event.set()
            self.stop_event.set()
        else:
            log.warning("Requested disconnect. But not connected.")
        await self.gctx['datastore'].update(self.handle, 'connected', False)
        return True

    async def load_file(self, filename):
        self.gcodefile = filename
        await self.gctx['datastore'].update(self.handle, 'selected', filename)
        return True

    async def send(self, gcode, wait_for_ack=True):
        gcode = gcode.strip()
        if not gcode: return True
        async with self.sendlock:
            log.debug("command {}: '{}'".format(self.cfg['name'], gcode))
            if not self.handler: return True ## can be true after each await!
            ## A command can be injected before the abort. But the abort executed first
            ## making the device never ack the injected code. So don't allow blocking
            ## in an emergency.
            if self.forceful_stop and wait_for_ack: return True

            if wait_for_ack:
                ## construct linenumber + checksum
                self.linenumber += 1
                ln = self.linenumber
                with_ln = "N{} {}".format(ln, gcode).encode()
                cs = functools.reduce(lambda a,b: a^b, with_ln)
                with_cs = "N{} {}*{}\n".format(ln, gcode, cs).encode()
                with_cs = "{}\n".format(gcode).encode()
                print(with_cs)

                ## ZMORPH has no buffer!
                ## Zmorph takes exactly .5 seconds to respond:b 

                for i in range(3):
                    self.handler.write(with_cs)
                    ## wait for response
                    log.debug("Waiting for device to acknowledge GCODE.")
                    await self.response_event.wait()
                    self.response_event.clear()
                    if not self.resent: break
                    log.warning("Resending GCODE")
                    self.resent = False
                    ## TODO if resent N>linenumber abort or resync.
                else:
                    log.critical("Devices asked for resend 3 times. Stopping.")
                    return False
            else:
                self.handler.write((gcode+'\n').encode())
                print((gcode+'\n').encode())
        return True


    async def replay_abort_gcode(self):
        log.warning("Print job aborted.")
        if self.forceful_stop:
            if 'abort_gcodes' in self.cfg:
                gcodes = self.cfg['abort_gcodes']
                for gcode in gcodes.split(';'):
                    log.debug("Sending GCODE: \"{}\"".format(gcode))
                    await self.send(gcode, wait_for_ack=False)
            await self.disconnect()
            await asyncio.sleep(1) ## allow device to recover
            await self.connect()
        else:
            if 'stop_gcodes' in self.cfg:
                gcodes = self.cfg['stop_gcodes']
                for gcode in gcodes.split(';'):
                    if self.forceful_stop: break
                    log.debug("Sending GCODE: \"{}\"".format(gcode))
                    await self.send(gcode)

    @plugin_hook
    async def gcode_readline_hook(self, line):
        return line

    @plugin_hook
    async def gcode_open_hook(self, filename):
        await self.store('paused', False)
        await self.store('idle', False)
        return filename
    
    @plugin_hook
    async def gcode_done_hook(self):
        await self.store('idle', True)

    async def inject(self, gcode):
        return await self.send(gcode)

    async def replay_gcode(self, gcodefile):
        self.stop_event.clear()
        self.resume_event.set()
        self.is_printing = True
        self.forceful_stop = False
        #await self.send("M110 N0", wait_for_ack=False)
        ## zmorph (firmware?)
        #await self.send("N0 M110", wait_for_ack=False)
        self.linenumber = 0
        with open(await self.gcode_open_hook(gcodefile)) as fd:
            for line in fd:
                line = await self.gcode_readline_hook(line)
                idx = line.find(';')
                if idx>=0: line = line[:idx]
                if not await self.send(line):
                    log.critical("Failed to send command, aborting.")
                    self.stop_event.set()

                if not self.resume_event.is_set():
                    log.debug("Device paused. Waiting for resume.")
                    await self.resume_event.wait()

                if self.stop_event.is_set():
                    log.debug("We need to stop")
                    ## do not do this if not connected
                    if self.handler:
                        log.debug("emergency gcode")
                        await self.replay_abort_gcode()
                    break

        log.debug("Print job stopped.")
        self.is_printing = False
        await self.gcode_done_hook()

    async def start(self): ## rename print file?
        ## TODO start should take file as argument. The gui should keep selection
        ## information.
        if not self.gcodefile:
            log.warning("Asking for start but no gcode file selected.")
            return False ## emit warning
        if not self.handler: return False
        if self.is_printing: return False
        #await asyncio.sleep(1) # make sure printer is done with init msgs
        self.gcode_task = asyncio.ensure_future(functools.partial(self.replay_gcode, self.gcodefile)())
        return True

    async def pause(self):
        self.resume_event.clear()
        await self.store('paused', True)
        return True

    async def resume(self):
        self.resume_event.set()
        await self.store('paused', False)
        return True

    async def abort(self):
        self.forceful_stop = True
        ## pretend the device acknowledged so we can continue sending the abort.
        self.response_event.set()
        self.stop_event.set()
        return True

    async def stop(self):
        ## make sure the device will stop
        self.stop_event.set()
        ## unpause
        await self.resume()
        return True

