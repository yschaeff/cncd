#!/usr/bin/python3

import asyncio, concurrent
import tui
from functools import partial
import logging as log
import shlex
import argparse, time, subprocess

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
                assert(nonce in self.waiters) # remove me!
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
        loop = asyncio.get_event_loop()
        loop.stop()

class Controller():
    def __init__(self, protocol):
        self.protocol = protocol

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

    def get_actions(self, gui_cb):
        def controller_cb(lines):
            actions = []
            for line in lines:
                cmd, label, description = shlex.split(line)
                actions.append( (cmd, label, description) )
            gui_cb(actions)
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
        self.protocol.send_message("stat", controller_cb)

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

    def start(self, gui_cb, device):
        def controller_cb(lines):
            if gui_cb:
                gui_cb(lines)
        self.protocol.send_message("start \"{}\"".format(device), controller_cb)

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

    def load(self, gui_cb, device, filename):
        def controller_cb(lines):
            if gui_cb:
                gui_cb(lines)
        self.protocol.send_message("load \"{}\" \"{}\"".format(device, filename), controller_cb)

    def start_logs(self, gui_cb):
        def controller_cb(lines):
            if gui_cb:
                gui_cb(lines)
        self.protocol.send_message("tracelog start", controller_cb, flush=True)

    def stop_logs(self):
        self.protocol.send_message("tracelog stop", flush=True)

def main(loop, args):
    CFG_DEFAULTS =  {'general':{
        'shell_pre': "",
        'shell_post': "",
        'unix_socket': '/tmp/cncd.sock',
        'config': './cnc.conf',
    }}

    from configparser import ConfigParser
    cfg = ConfigParser()
    cfg.read_dict(CFG_DEFAULTS)
    general = cfg['general']
    ## first overwrite config location with cfg supplied on commandline
    if args.config:
        general['config'] = args.config
    ## Then open config
    if not cfg.read(general["config"]):
        log.info("Could not load any configuration file, continue with defaults.")

    ## Now, let anything in args overwrite defaults
    for arg, value in vars(args).items():
        if value == None: continue
        log.debug("Overwriting default value for {} with {}".format(arg, value))
        general[arg] = str(value)

    if general['shell_pre']:
        pre = subprocess.Popen(shlex.split('"{}"'.format(general['shell_pre'])))
        if general['shell_pre_sleep']:
            time.sleep(float(general['shell_pre_sleep']))

    socketpath = general['unix_socket']
    future = loop.create_unix_connection(partial(CncProtocol), socketpath)
    try:
        transport, protocol = loop.run_until_complete(future)
    except ConnectionRefusedError as e:
        log.critical("Unable to set up connection")
        if general['shell_pre']:
            pre.kill()
        if general['shell_post']:
            post = subprocess.Popen(shlex.split('"{}"'.format(general['shell_post'])))
        return
    except FileNotFoundError as e:
        log.critical("Unix domain socket '{}' might not exist.".format(socketpath))
        if general['shell_pre']:
            pre.kill()
        if general['shell_post']:
            post = subprocess.Popen(shlex.split('"{}"'.format(general['shell_post'])))
        return

    controller = Controller(protocol)

    with tui.Tui(loop, controller) as utui:
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            pass #graceful exit

    if protocol.gui_exception:
        log.critical("Exception raised in GUI callback function:")
        if general['shell_pre']:
            pre.kill()
        if general['shell_post']:
            post = subprocess.Popen(shlex.split('"{}"'.format(general['shell_post'])))
        raise protocol.gui_exception
    log.debug("terminating")
    transport.close()
    pending = asyncio.Task.all_tasks()
    for task in pending: task.cancel()
    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    if general['shell_pre']:
        pre.kill()
    if general['shell_post']:
        post = subprocess.Popen(shlex.split('"{}"'.format(general['shell_post'])))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", action="store")
    parser.add_argument("-u", "--unix-socket", help="Path to server socket",
            action="store")
    parser.add_argument("-l", "--log-level",
            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            type=str.upper, action="store", default='WARNING')
    args = parser.parse_args()

    log.basicConfig(level=args.log_level)
    loop = asyncio.get_event_loop()
    main(loop, args)
    loop.close()
