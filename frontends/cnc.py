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

def main(loop, args):
    cfg = ConfigParser()
    cfgfile = expanduser(args.config)
    if not cfg.read(cfgfile):
        log.critical("Could not open configuration file ({})".format(args.config))
        return
    if not args.instance in cfg.sections():
        log.critical("No configuration for '{}' found.".format(args.instance))
        log.critical("Available: '{}'".format(cfg.sections()))
        return
    if not cfg.has_section(args.instance):
        log.critical("No configuration section '[{}]' found.".format(args.instance))
        return

    shell_pre = cfg.get(args.instance, 'shell_pre', fallback=None)
    shell_pre_sleep = cfg.get(args.instance, 'shell_pre_sleep', fallback=None)
    shell_post = cfg.get(args.instance, 'shell_post', fallback=None)
    unix_socket = cfg.get(args.instance, 'unix_socket', fallback="")

    if shell_pre:
        pre = subprocess.Popen(shlex.split('"{}"'.format(shell_pre)))
        if shell_pre_sleep: time.sleep(float(shell_pre_sleep))

    socketpath = unix_socket
    future = loop.create_unix_connection(CncProtocol, unix_socket)
    try:
        transport, protocol = loop.run_until_complete(future)
    except ConnectionRefusedError as e:
        log.critical("Unable to set up connection for [{}] to '{}'".format(args.instance, socketpath))
        if shell_pre: pre.kill()
        if shell_post: post = subprocess.Popen(shlex.split('"{}"'.format(shell_post)))
        return
    except FileNotFoundError as e:
        log.critical("Unix domain socket '{}' might not exist.".format(socketpath))
        if shell_pre: pre.kill()
        if shell_post: post = subprocess.Popen(shlex.split('"{}"'.format(shell_post)))
        return

    controller = Controller(protocol)

    with tui.Tui(loop, controller) as utui:
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            pass #graceful exit

    if protocol.gui_exception:
        log.critical("Exception raised in GUI callback function:")
        if shell_pre: pre.kill()
        if shell_post: post = subprocess.Popen(shlex.split('"{}"'.format(shell_post)))
        raise protocol.gui_exception
    log.debug("terminating")
    transport.close()
    pending = asyncio.Task.all_tasks()
    for task in pending: task.cancel()
    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    if shell_pre: pre.kill()
    if shell_post: post = subprocess.Popen(shlex.split('"{}"'.format(shell_post)))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("instance", metavar="INSTANCE", nargs='?', action="store",
            default="default", help="Instance to connect to. ('default' when not specified)")
    parser.add_argument("-c", "--config", action="store", default='~/.config/cnc.conf')
    parser.add_argument("-l", "--log-level",
            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            type=str.upper, action="store", default='WARNING')
    args = parser.parse_args()

    log.basicConfig(level=args.log_level)
    loop = asyncio.get_event_loop()
    main(loop, args)
    loop.close()
