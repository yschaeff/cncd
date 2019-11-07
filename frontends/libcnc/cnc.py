#!/usr/bin/python3

import asyncio, concurrent
import tui
from functools import partial
from collections import defaultdict
import logging as log
import shlex, json
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
        """ If flush is set to True, the response_handler is called for
            every received line instead of waiting for the entire message.
            Usefull for monitoring over longer periods."""
        self.transport.write("{} {}\n".format(self.nonce, message).encode())
        self.waiters[self.nonce] = (response_handler, [], flush)
        self.nonce += 1
    def connection_made(self, transport):
        self.transport = transport
    def data_received(self, data):
        log.debug("received: " + str( data))
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
            elif flush and handler:
                handler([line])
            else:
                buf.append(line)
    def error_received(self, exc):
        pass
    def connection_lost(self, exc):
        ## TODO this might not do what we want?
        log.info("Connection lost.")
        loop = asyncio.get_event_loop()
        loop.stop()

class Controller():
    def __init__(self, protocol, sync_method):
        self.protocol = protocol
        self.filenames = defaultdict(str)
        self.sync_method = sync_method
        self.hello()

    def set_filename(self, device, filename):
        self.filenames[device] = filename
    def get_filename(self, device):
        return self.filenames[device]

    def cb(self, gui_cb, msgs):
        if not gui_cb: return
        if msgs:
            for msg in msgs:
                try:
                    json_msg = json.loads(msg)
                except json.decoder.JSONDecodeError as e:
                    json_msg = {'ERROR': str(e) }
                gui_cb(json_msg)
        else: ## An empty response is still a response!
            gui_cb({})

    def get_devlist(self, gui_cb):
        cmd = "devlist"
        self.protocol.send_message(cmd, partial(self.cb, gui_cb))

    def action(self, cmd, gui_cb):
        self.protocol.send_message(cmd, partial(self.cb, gui_cb))

    def hello(self):
        def controller_cb(jmsg):
            self.cncd_version = int(jmsg.get('version', 0))
            self.api_version = int(jmsg.get('api', 0))
            self.time_offset = time.time() - float(jmsg.get('time', time.time()))
        self.time_offset = 0
        self.cncd_version = 0
        self.api_version = 0
        cmd = "hello"
        self.protocol.send_message(cmd, partial(self.cb, controller_cb))

    def get_actions(self, gui_cb):
        cmd = "actions"
        self.protocol.send_message(cmd, partial(self.cb, gui_cb))

    def get_camlist(self, gui_cb):
        cmd = "camlist"
        self.protocol.send_message(cmd, partial(self.cb, gui_cb))

    def get_data(self, gui_cb, device):
        cmd = "data \"{}\"".format(device)
        self.protocol.send_message(cmd, partial(self.cb, gui_cb))

    def subscribe(self, gui_cb, device):
        cmd = "subscribe \"{}\"".format(device)
        self.protocol.send_message(cmd, partial(self.cb, gui_cb), flush=True)

    def unsubscribe(self, gui_cb, device):
        cmd = "unsubscribe \"{}\"".format(device)
        self.protocol.send_message(cmd, partial(self.cb, gui_cb))

    def get_filelist(self, gui_cb, device):
        cmd = "stat \"{}\"".format(device)
        self.protocol.send_message(cmd, partial(self.cb, gui_cb))

    def connect(self, gui_cb, device):
        cmd = "connect \"{}\"".format(device)
        self.protocol.send_message(cmd, partial(self.cb, gui_cb))

    def disconnect(self, gui_cb, device):
        cmd = "disconnect \"{}\"".format(device)
        self.protocol.send_message(cmd, partial(self.cb, gui_cb))

    def start(self, gui_cb, device, filename):
        cmd ="start \"{}\" \"{}\"".format(device, filename)
        self.protocol.send_message(cmd, partial(self.cb, gui_cb))

    def abort(self, gui_cb, device):
        cmd = "abort \"{}\"".format(device)
        self.protocol.send_message(cmd, partial(self.cb, gui_cb))

    def stop(self, gui_cb, device):
        cmd = "stop \"{}\"".format(device)
        self.protocol.send_message(cmd, partial(self.cb, gui_cb))

    def pause(self, gui_cb, device):
        cmd = "pause \"{}\"".format(device)
        self.protocol.send_message(cmd, partial(self.cb, gui_cb))

    def resume(self, gui_cb, device):
        cmd = "resume \"{}\"".format(device)
        self.protocol.send_message(cmd, partial(self.cb, gui_cb))

    def start_logs(self, gui_cb):
        cmd = "tracelog start"
        self.protocol.send_message(cmd, partial(self.cb, gui_cb), flush=True)

    def stop_logs(self):
        cmd = "tracelog stop"
        self.protocol.send_message(cmd, None)

    def sync(self):
        log.debug(f"trying to sync with command {self.sync_method}")
        if self.sync_method:
            proc = subprocess.Popen(shlex.split('"{}"'.format(self.sync_method)), stdout=subprocess.PIPE, stdin=subprocess.PIPE)
            return proc.stdout.readlines()
        return None

def connect(loop, path):
    future = loop.create_unix_connection(CncProtocol, path)
    try:
        transport, protocol = loop.run_until_complete(future)
    except ConnectionRefusedError as e:
        log.critical("Unable to set up connection to '{}'".format(path))
        return None
    except FileNotFoundError as e:
        log.critical("Unix domain socket '{}' might not exist.".format(path))
        return None
    return (transport, protocol)

