import logging as log
import asyncio, functools, concurrent
import serial
import serial_asyncio
import os, re, traceback

from pluginmanager import plugin_hook
import flavour

class DummySerialConnection():
    def __init__(self, device, rx_queue):
        self.rx_queue = rx_queue
        self.device = device
        device.set_protocol(self)
        self.write("> Dummy console")
    def close(self):
        log.info("Dummy serial connection closed")
        asyncio.ensure_future(self.device.disconnect_done(None))
    def write(self, msg):
        async def slow_ack():
            await asyncio.sleep(.01)
            await self.rx_queue.put("ok\n")
        task = asyncio.ensure_future(slow_ack())

class CncConnection(asyncio.Protocol):
    """Implements protocol"""
    def __init__(self, device, rx_queue):
        super().__init__()
        self.rx_queue = rx_queue
        self.device = device
        device.set_protocol(self)
        self.input_buffer = ""
    def connection_made(self, transport):
        self.transport = transport
    def data_received(self, data):
        self.input_buffer += data.decode()
        while True:
            index = self.input_buffer.find('\n')
            if index < 0: break
            line = self.input_buffer[:index+1]
            self.input_buffer = self.input_buffer[index+1:]
            self.rx_queue.put_nowait(line) ## rx queue is unbounded so this is safe
    def connection_lost(self, exc):
        asyncio.ensure_future(self.device.disconnect_done(exc))
    def close(self):
        self.transport.close()
    def write(self, msg):
        self.transport.write(msg.encode())

class Device():
    """General CNC device, keeps state, buffers etc"""
    def __init__(self, handle, dev_cfg, gctx):
        self.handle = handle
        self.cfg = dev_cfg
        self.gctx = gctx
        self.ev_connected = asyncio.Event()

        self.file_task = None
        self.panic_mode = False

        self.firmware = flavour.get_firmware(self.cfg.get('firmware', 'generic'))
        asyncio.ensure_future(self.store('paused', False))
        asyncio.ensure_future(self.store('idle', True))
        asyncio.ensure_future(self.store('connected', False))

    def set_protocol(self, proto):
        self.protocol = proto

    def get_name(self):
        return self.cfg['name']

    async def store(self, key, value):
        await self.gctx['datastore'].update(self.handle, key, value)

    async def connect(self):
        if self.ev_connected.is_set():
            log.warning("already connected")
            return False
        self.ack_queue = asyncio.Queue(self.firmware.max_buffer_lenght)
        self.tx_queue = asyncio.Queue(1)
        rx_queue = asyncio.Queue()
        is_alive = asyncio.Event()

        await self.store('idle', True)

        self.ev_resume = asyncio.Event()
        self.ev_resume.set()
        self.panic_mode = False

        port_spec = re.compile("^(.+)://(.+)[@:]([0-9]+)$")
        port = self.cfg["port"].strip()
        if not port_spec.match(port):
            log.error("port property in configuration not parsable.")
            return False

        def connect_cb(ev_done, ev_connected, future):
            try:
                r = future.result()
            except concurrent.futures._base.CancelledError:
                log.debug('Connect task cancelled')
            except FileNotFoundError as e:
                log.error(str(e))
            except serial.serialutil.SerialException as e:
                log.error(str(e))
            except OSError as e:
                log.error(str(e))
            except Exception as e:
                log.critical("Unhandled exception: {}".format(str(e)))
                log.critical(traceback.format_exc())
            else:
                ev_connected.set()
            finally:
                ev_done.set()

        log.info("device '{}' trying to connect...".format(self.get_name()))
        ## the result must have three groups exactly"
        proto, addr, param = port_spec.findall(port)[0] ## we can only have one
        ev_done = asyncio.Event()
        loop = self.gctx['loop']
        if proto == 'dummy':
            DummySerialConnection(self, rx_queue)
            ev_done.set()
            self.ev_connected.set()
        elif proto == 'serial':
            coro = serial_asyncio.create_serial_connection(loop,
                functools.partial(CncConnection, self, rx_queue), addr, baudrate=param)
            self.tx_task = asyncio.ensure_future(coro)
            self.tx_task.add_done_callback(functools.partial(connect_cb, ev_done, self.ev_connected))
        elif proto == 'tcp':
            coro = loop.create_connection(
                functools.partial(CncConnection, self, rx_queue), addr, param)
            self.tx_task = asyncio.ensure_future(coro)
            self.tx_task.add_done_callback(functools.partial(connect_cb, ev_done, self.ev_connected))
        else:
            log.error("can't understand portspec")
            return False

        await ev_done.wait()
        if not self.ev_connected.is_set():
            log.error("Failed to connect.")
            return False
        await self.store('connected', True)

        self.tx_task = asyncio.ensure_future(self.sender(self.tx_queue, self.ack_queue, is_alive))
        self.tx_task.add_done_callback(self.task_done)
        self.rx_task = asyncio.ensure_future(self.receiver(rx_queue, self.ack_queue, is_alive))
        self.rx_task.add_done_callback(self.task_done)
        return True

    def task_done(self, future):
        """Generic callback for tasks"""
        try:
            r = future.result()
        except concurrent.futures._base.CancelledError:
            log.debug('com task cancelled')
        except Exception as e:
            log.critical(str(e))
            log.critical(traceback.format_exc())
            self.gctx['loop'].stop()

    @plugin_hook
    async def connect_done(self):
        """Callback from sender"""
        log.info("device '{}' connected".format(self.get_name()))

    @plugin_hook
    async def disconnect_done(self, exc):
        """Callback from protocol"""
        log.info("device '{}' disconnected".format(self.get_name()))
        if self.ev_connected.is_set():
            ## hmm, maybe the cable unplugged?
            await self.disconnect()
        await self.store('connected', False)

    async def disconnect(self):
        if not self.ev_connected.is_set():
            log.warning("not connected")
            return False
        self.ev_connected.clear()
        self.tx_task.cancel()
        self.rx_task.cancel()
        self.protocol.close()
        return True

    async def sender(self, tx_queue, ack_queue, is_alive):
        log.debug("waiting for alive")
        await is_alive.wait()
        await self.connect_done()
        log.debug("start sender")
        while True:
            line = await tx_queue.get()
            await self.ev_resume.wait()
            if not self.panic_mode:
                await ack_queue.put(line)
            log.debug("Outgoing: '{}'".format(line))
            self.protocol.write(line+'\n')
            self.tx_queue.task_done()

    @plugin_hook
    async def rx_hook(self, line):
        pass

    async def receiver(self, rx_queue, ack_queue, is_alive):
        while True:
            line = self.firmware.strip_prompt(await rx_queue.get())
            await self.rx_hook(line)
            log.debug("Incoming: '{}'".format(line))
            is_alive.set()
            if self.firmware.is_ack(line):
                if not ack_queue.empty():
                    _ = await ack_queue.get()
            elif self.firmware.is_error(line):
                if not ack_queue.empty():
                    _ = await ack_queue.get()


    async def inject(self, gcode):
        if not self.ev_connected.is_set():
            log.warning("not connected")
            return False
        await self.tx_queue.put(gcode)
        return True

    @plugin_hook
    async def gcode_open_hook(self, filename):
        log.info("Device '{}' starts working on file '{}'".format(self.get_name(), filename))
        return filename

    @plugin_hook
    async def gcode_readline_hook(self, line):
        return line

    @plugin_hook
    async def gcode_done_hook(self):
        log.info("Device '{}' stopped working on file".format(self.get_name()))

    async def start_task(self, filename):
        def strip_comments(line):
            line = line.decode()
            idx = line.find(';')
            if idx < 0:
                return line.strip()
            else:
                return line[:idx].strip()

        await self.store('idle', False)
        with open(await self.gcode_open_hook(filename), 'rb') as fd:
            for line in fd:
                line = strip_comments(await self.gcode_readline_hook(line))
                if not line: continue
                await self.tx_queue.put(line)
        log.info("Device '{}' stops working on file '{}'".format(self.get_name(), filename))

    def start_task_cb(self, future):
        try:
            r = future.result()
        except FileNotFoundError:
            log.warning("File not found")
        except concurrent.futures._base.CancelledError:
            log.debug('start task cancelled')
        finally:
            self.file_task = None
            asyncio.ensure_future(self.store('idle', True))
            asyncio.ensure_future(self.gcode_done_hook())

    async def start(self, filename):
        if not self.ev_connected.is_set():
            log.warning("not connected")
            return False
        if self.file_task: return False
        await self.resume()
        self.file_task = asyncio.ensure_future(self.start_task(filename))
        self.file_task.add_done_callback(self.start_task_cb)
        return True

    async def stop(self):
        if not self.ev_connected.is_set():
            log.warning("not connected")
            return False
        self.flush_queue(self.tx_queue)
        if self.file_task:
            self.file_task.cancel()
        await self.resume()
        for line in self.firmware.stop_gcodes:
            await self.tx_queue.put(line)
        return True

    def flush_queue(self, queue):
        while True:
            try:
                queue.get_nowait()
                queue.task_done()
            except asyncio.QueueEmpty:
                return

    async def abort(self):
        if not self.ev_connected.is_set():
            log.warning("not connected")
            return False
        log.warning("Device '{}' aborting".format(self.get_name()))
        self.flush_queue(self.tx_queue)
        self.flush_queue(self.ack_queue)
        if self.file_task:
            self.file_task.cancel()
        self.panic_mode = True
        await self.resume()
        for line in self.firmware.abort_gcodes:
            await self.tx_queue.put(line)
        await self.tx_queue.join()
        self.panic_mode = False
        await self.disconnect()
        return True

    async def pause(self):
        if not self.ev_connected.is_set():
            log.warning("not connected")
            return False
        self.ev_resume.clear()
        await self.store('paused', True)
        log.info("Device '{}' paused".format(self.get_name()))
        return True

    async def resume(self):
        if not self.ev_connected.is_set():
            log.warning("not connected")
            return False
        self.ev_resume.set()
        await self.store('paused', False)
        log.info("Device '{}' resumed".format(self.get_name()))
        return True
