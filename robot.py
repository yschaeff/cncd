import logging as log
import asyncio, functools, concurrent
import serial
import serial_asyncio

class DummySerialConnection():
    def __init__(self, device):
        self.device = device
        device.handler = self
    def close(self):
        self.device.handler = None
        log.info("Dummy serial connection closed")
    def write(self, msg):
        log.info("Dummy serial connection write")
        async def slow_ack():
            await asyncio.sleep(.1)
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
        self.name = dev_cfg['name']
        log.info("Added device \"{}\"".format(self.name))
        self.connected = False
        self.gcodefile = None
        self.handler = None
        self.input_buffer = b''
        self.gcode_task = None
        self.dummy = (dev_cfg["port"] == "dummy")

    def rx(self, data):
        self.input_buffer += data
        while True:
            index = self.input_buffer.find(b'\n')
            if index < 0: break
            line  = self.input_buffer[:index+1]
            self.input_buffer = self.input_buffer[index+1:]
            log.debug("robot says '{}'".format(line.decode().strip()))
            if line.decode().strip() == 'ok':
                self.response_event.set()
            elif line.decode().strip() == 'ERROR':
                self.respnse_event.set()

    def status(self):
        s = "connected {}".format(self.handler != None)
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

    async def connect(self):
        ## create serial server:
        def done_cb(event, device, future):
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
            log.error("Unable to open serial device.")
        return self.success

    def disconnect(self):
        if self.handler:
            self.handler.expect_close = True
            self.handler.close()
        else:
            log.warning("Requested disconnect. But not connected.")
        return True
    def load_file(self, filename):
        self.gcodefile = filename
        return True

    async def replay_gcode(self):
        with open(self.gcodefile) as fd:
            for line in fd:
                idx = line.rfind(';')
                if idx>=0: line = line[:idx]
                gcode = line.strip()
                if not gcode: continue
                log.debug("simon says '{}'".format(gcode))
                self.handler.write((gcode+'\n').encode())
                ## wait for response
                await self.response_event.wait()
                self.response_event.clear()

    async def start(self): ## rename print file?
        if not self.gcodefile:
            log.warning("Asking for start but no gcode file selected.")
            return False ## emit warning
        if not self.handler: return False
        #await asyncio.sleep(1) # make sure printer is done with init msgs
        self.gcode_task = asyncio.ensure_future(self.replay_gcode())
        return True

    def pause(self):
        pass

    async def stop(self):
        if self.gcode_task:
            self.gcode_task.cancel()
        return True

