import logging as log
import asyncio, functools, concurrent
import serial
import serial_asyncio

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
                #self.transport.loop.stop()

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

