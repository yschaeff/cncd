import logging as log
import asyncio, functools, concurrent
import serial
import serial_asyncio
import os
from pluginmanager import plugin_hook

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
            self.device.rx(b'ok\n')
        task = asyncio.ensure_future(slow_ack())

class SerialConnection(asyncio.Protocol):
    """Implements protocol"""
    def __init__(self, device):
        self.device = device
        device.handler = self
        self.expect_close = False
        super().__init__()

    def connection_made(self, transport):
        self.transport = transport
        log.info("Serial port {} opened".format(transport.serial.name))
        log.debug('Serial properties: {}'.format(transport))
        #transport.write(b'Hello, World!\n')  # Write serial data via transport

    def data_received(self, data):
        self.device.rx(data)

    def connection_lost(self, exc):
        if not self.expect_close:
            log.error('Serial device vanished!')
        else:
            log.info('Serial port closed')
        self.device.handler = None

    def pause_writing(self):
        print('pause writing')
        print(self.transport.get_write_buffer_size())

    def resume_writing(self):
        print(self.transport.get_write_buffer_size())
        print('resume writing')

    def close(self):
        self.transport.close()
    def write(self, msg):
        self.transport.write(msg)


class Device():
    """General CNC device, keeps state, buffers etc"""
    def __init__(self, dev_cfg, gctx):
        self.cfg = dev_cfg
        self.gctx = gctx
        self.con = None
        log.info("Added device \"{}\"".format(self.cfg['name']))
        self.connected = False
        self.gcodefile = None
        self.handler = None
        self.input_buffer = b''
        self.gcode_task = None
        self.dummy = (dev_cfg["port"] == "dummy")
        self.is_printing = False
        self.printing_file = ""
        self.stop_event = asyncio.Event()
        self.resume_event = asyncio.Event()
        self.response_event = asyncio.Event()
        self.resume_event.set() ## start not paused

    def update_cfg(self, dev_cfg):
        self.cfg = dev_cfg

    def get_name(self):
        return self.cfg['name']

    def rx(self, data):
        self.input_buffer += data
        while True:
            index = self.input_buffer.find(b'\n')
            if index < 0: break
            line  = self.input_buffer[:index+1]
            self.input_buffer = self.input_buffer[index+1:]
            log.debug("response {}: '{}'".format(self.cfg['name'], line.decode().strip()))
            if line.decode().strip() == 'ok':
                self.response_event.set()
            elif line.decode().strip() == 'ERROR':
                self.respnse_event.set()

    def status(self):
        c = (self.handler != None)
        p = self.is_printing
        Te = ""
        TSe = ""
        Tb = ""
        TSb = ""
        fstaged = self.gcodefile
        fprinting = self.printing_file
        paused = not self.resume_event.is_set()

        s  =  "connected:{}".format(c)
        s += " printing:{}".format(p)
        s += " Textruder:{}/{}".format(Te, TSe)
        s += " Tbed:{}/{}".format(Tb, TSb)
        s += " file:\"{}\"".format(fprinting)
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
        self.success = False
        loop = asyncio.get_event_loop()
        if not self.dummy:
            coro = serial_asyncio.create_serial_connection(loop, functools.partial(SerialConnection, self),
                self.cfg["port"], baudrate=self.cfg["baud"])
            task = asyncio.ensure_future(coro)
            task.add_done_callback(functools.partial(done_cb, event, self))
            await event.wait()
        else:
            DummySerialConnection(self)
            self.success = True
        if self.success:
            log.info("Serial device connected successfully.")
            self.input_buffer = b''
        else:
            log.error("Unable to connect to serial device.")
        return self.success

    @plugin_hook
    async def disconnect(self):
        if self.handler:
            self.resume()
            self.handler.expect_close = True
            self.handler.close()
            self.response_event.set()
            self.stop_event.set()
        else:
            log.warning("Requested disconnect. But not connected.")
        return True

    def load_file(self, filename):
        self.gcodefile = filename
        return True

    async def send(self, gcode, wait_for_ack=True):
        gcode = gcode.strip()
        if not gcode: return
        log.debug("command {}: '{}'".format(self.cfg['name'], gcode))
        self.handler.write((gcode+'\n').encode())
        ## wait for response
        if wait_for_ack:
            log.debug("Waiting for device to acknowledge GCODE.")
            await self.response_event.wait()
            log.debug("Ack!")
            self.response_event.clear()

    async def replay_abort_gcode(self):
        log.warning("Print job aborted.")
        if self.forceful_stop:
            if 'abort_gcodes' in self.cfg:
                gcodes = self.cfg['abort_gcodes']
                for gcode in gcodes.split(';'):
                    log.debug("Sending GCODE: \"{}\"".format(gcode))
                    await self.send(gcode, wait_for_ack=False)
            await self.disconnect()
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
        return filename

    async def replay_gcode(self):
        self.stop_event.clear()
        self.resume_event.set()
        self.is_printing = True
        self.printing_file = self.gcodefile
        self.forceful_stop = False
        with open(await self.gcode_open_hook(self.gcodefile)) as fd:
            for line in fd:
                line = await self.gcode_readline_hook(line)
                idx = line.rfind(';')
                if idx>=0: line = line[:idx]
                await self.send(line)
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

        self.printing_file = ""
        log.debug("Print job stopped.")
        self.is_printing = False

    async def start(self): ## rename print file?
        if not self.gcodefile:
            log.warning("Asking for start but no gcode file selected.")
            return False ## emit warning
        if not self.handler: return False
        if self.is_printing: return False
        #await asyncio.sleep(1) # make sure printer is done with init msgs
        self.gcode_task = asyncio.ensure_future(self.replay_gcode())
        return True

    def pause(self):
        self.resume_event.clear()
        return True

    def resume(self):
        self.resume_event.set()
        return True

    async def abort(self):
        self.forceful_stop = True
        await self.stop()
        ## pretend the device acknowledged so we can continue sending the abort.
        self.response_event.set()

    async def stop(self):
        ## make sure the device will stop
        self.stop_event.set()
        ## unpause
        self.resume()
        return True

