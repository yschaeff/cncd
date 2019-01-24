#!/usr/bin/python3

import asyncio, concurrent
import tui
from functools import partial
from collections import defaultdict
import logging as log
import shlex
import argparse, time, subprocess
from configparser import ConfigParser
from os.path import expanduser

class CncProtocol(asyncio.Protocol):
    def __init__(self):
        self.waiters = {}
        self.nonce = 1
        self.data = ""
        self.gui_exception = None
    def send_message(self, message, response_handler = None, flush=False):
        self.transport.write("{} {}\n".format(self.nonce, message).encode())
        self.waiters[self.nonce] = (response_handler, [], flush)
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
                continue
            handler, buf, flush = self.waiters[nonce]
            if line.strip() == ".":
                if handler:
                    try:
                        handler(buf)
                    except Exception as e:
                        self.gui_exception = e
                        self.transport.close()
                self.waiters.pop(nonce)
            elif flush:
                handler([line])
            else:
                buf.append(line)
    def error_received(self, exc):
        pass
    def connection_lost(self, exc):
        ## TODO this might not do what we want?
        loop = asyncio.get_event_loop()
        loop.stop()

class Controller():
    def __init__(self, protocol):
        self.protocol = protocol
        self.filenames = defaultdict(str)
        self.hello()

    def set_filename(self, device, filename):
        self.filenames[device] = filename
    def get_filename(self, device):
        return self.filenames[device]

    def get_devlist(self, gui_cb):
        def controller_cb(lines):
            devices = []
            for line in lines:
                locator, name = shlex.split(line)
                devices.append( (locator, name) )
            gui_cb(devices)
        self.protocol.send_message("devlist", controller_cb)

    def action(self, cmd, gui_cb):
        self.protocol.send_message(cmd, None)

    def hello(self):
        self.time_offset = 0
        self.cncd_version = 0
        self.api_version = 0
        def controller_cb(lines):
            for line in lines:
                r = line.split()
                if len(r) != 2: continue
                key, value = r
                if key == 'version':
                    self.cncd_version = int(value)
                elif key == 'api':
                    self.api_version = int(value)
                elif key == 'time':
                    self.time_offset = time.time() - float(value)
        self.protocol.send_message("hello", controller_cb)

    def get_actions(self, gui_cb):
        def controller_cb(lines):
            gui_cb(lines)
        self.protocol.send_message("actions", controller_cb)

    def get_camlist(self, gui_cb):
        def controller_cb(lines):
            webcams = []
            for line in lines:
                locator, name, url = shlex.split(line)
                webcams.append( (locator, name, url) )
            gui_cb(webcams)
        self.protocol.send_message("camlist", controller_cb)

    def get_data(self, gui_cb, device):
        def controller_cb(lines):
            gui_cb(lines)
        self.protocol.send_message("data \"{}\"".format(device), controller_cb)

    def subscribe(self, gui_cb, device):
        def controller_cb(lines):
            gui_cb(lines)
        self.protocol.send_message("subscribe \"{}\"".format(device), controller_cb, flush=True)

    def unsubscribe(self, gui_cb, device):
        self.protocol.send_message("unsubscribe \"{}\"".format(device))

    def get_filelist(self, gui_cb, device):
        def controller_cb(lines):
            gui_cb(lines)
        self.protocol.send_message("stat \"{}\"".format(device), controller_cb)

    def connect(self, gui_cb, device):
        def controller_cb(lines):
            if gui_cb:
                gui_cb(lines)
        self.protocol.send_message("connect \"{}\"".format(device), controller_cb)

    def disconnect(self, gui_cb, device):
        def controller_cb(lines):
            if gui_cb:
                gui_cb(lines)
        self.protocol.send_message("disconnect \"{}\"".format(device), controller_cb)

    def start(self, gui_cb, device, filename):
        def controller_cb(lines):
            if gui_cb:
                gui_cb(lines)
        self.protocol.send_message("start \"{}\" \"{}\"".format(device, filename), controller_cb)

    def abort(self, gui_cb, device):
        def controller_cb(lines):
            if gui_cb:
                gui_cb(lines)
        self.protocol.send_message("abort \"{}\"".format(device), controller_cb)

    def stop(self, gui_cb, device):
        def controller_cb(lines):
            if gui_cb:
                gui_cb(lines)
        self.protocol.send_message("stop \"{}\"".format(device), controller_cb)

    def pause(self, gui_cb, device):
        def controller_cb(lines):
            if gui_cb:
                gui_cb(lines)
        self.protocol.send_message("pause \"{}\"".format(device), controller_cb)

    def resume(self, gui_cb, device):
        def controller_cb(lines):
            if gui_cb:
                gui_cb(lines)
        self.protocol.send_message("resume \"{}\"".format(device), controller_cb)

    def start_logs(self, gui_cb):
        def controller_cb(lines):
            if gui_cb:
                gui_cb(lines)
        self.protocol.send_message("tracelog start", controller_cb, flush=True)

    def stop_logs(self):
        self.protocol.send_message("tracelog stop", flush=True)

def connect(loop, path):
    future = loop.create_unix_connection(CncProtocol, path)
    try:
        transport, protocol = loop.run_until_complete(future)
    except ConnectionRefusedError as e:
        log.critical("Unable to set up connection for [{}] to '{}'".format(args.instance, socketpath))
        return None
    except FileNotFoundError as e:
        log.critical("Unix domain socket '{}' might not exist.".format(socketpath))
        return None
    return (transport, protocol)

