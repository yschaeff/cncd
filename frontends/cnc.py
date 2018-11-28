#!/usr/bin/python3

import asyncio, concurrent
import tui
from functools import partial
import logging as log

PATH = '../.cncd.sock'

class CncProtocol(asyncio.Protocol):
    def __init__(self):
        self.waiters = {}
        self.nonce = 1
        self.data = ""
    def send_message(self, message, response_handler = None):
        self.transport.write(f"{self.nonce} {message}\n".encode())
        self.waiters[self.nonce] = (response_handler, [])
        self.nonce += 1
    def connection_made(self, transport):
        self.transport = transport
    def data_received(self, data):
        ## accumulate data
        self.data += data.decode()
        while True:
            ## new complete line ready?
            idx = self.data.find('\n')
            if idx == -1: break
            line = self.data[:idx+1]
            self.data = self.data[idx+1:]
            ## great, find nonce
            nonce_separator = line.find(' ')
            if nonce_separator == -1: continue
            s_nonce = line[:nonce_separator]
            line = line[nonce_separator+1:]
            try:
                nonce = int(s_nonce)
            except ValueError:
                continue
            if nonce not in self.waiters:
                assert(nonce in self.waiters) # remove me!
                continue
            handler, buf = self.waiters[nonce]
            if line.strip() == ".":
                handler(buf)
                self.waiters.pop(nonce)
            else:
                buf.append(line)
    def error_received(self, exc):
        pass
    def connection_lost(self, exc):
        loop = asyncio.get_event_loop()
        loop.stop()

class Controller():
    def __init__(self, protocol):
        self.protocol = protocol

    def get_devlist(self, gui_cb):
        def controller_cb(lines):
            gui_cb(lines)
        self.protocol.send_message("devlist", controller_cb)

    def get_status(self, gui_cb, device):
        def controller_cb(lines):
            gui_cb(lines)
        self.protocol.send_message(f"status \"{device}\"", controller_cb)

    def get_filelist(self, gui_cb, device):
        def controller_cb(lines):
            gui_cb(lines)
        self.protocol.send_message(f"stat", controller_cb)

    def connect(self, gui_cb, device):
        def controller_cb(lines):
            if gui_cb:
                gui_cb(lines)
        self.protocol.send_message(f"connect \"{device}\"", controller_cb)

    def disconnect(self, gui_cb, device):
        def controller_cb(lines):
            if gui_cb:
                gui_cb(lines)
        self.protocol.send_message(f"disconnect \"{device}\"", controller_cb)

    def start(self, gui_cb, device):
        def controller_cb(lines):
            if gui_cb:
                gui_cb(lines)
        self.protocol.send_message(f"start \"{device}\"", controller_cb)

    def stop(self, gui_cb, device):
        def controller_cb(lines):
            if gui_cb:
                gui_cb(lines)
        self.protocol.send_message(f"stop \"{device}\"", controller_cb)

def main(loop):
    future = loop.create_unix_connection(partial(CncProtocol), PATH)
    try:
        transport, protocol = loop.run_until_complete(future)
    except ConnectionRefusedError as e:
        log.fatal("Unable to set up connection")
        return

    controller = Controller(protocol)

    with tui.Tui(loop, controller) as utui:
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            pass
    log.debug("terminating")
    transport.close()
    pending = asyncio.Task.all_tasks()
    for task in pending: task.cancel()
    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

if __name__ == '__main__':
    log.basicConfig(level=log.DEBUG)
    loop = asyncio.get_event_loop()
    main(loop)
    loop.close()
