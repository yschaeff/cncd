#!/usr/bin/python3

import asyncio, concurrent
import tui
from functools import partial
from collections import defaultdict
import logging as log
import shlex, sys
import argparse, time, subprocess
from configparser import ConfigParser
from os.path import expanduser

sys.path.append('..')
from libcnc.cnc import CncProtocol, Controller, connect

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

    def kill():
        if shell_pre:
            pre.kill()
        if shell_post:
            post = subprocess.Popen(shlex.split('"{}"'.format(shell_post)))

    socketpath = unix_socket
    result = connect(loop, socketpath)
    if not result:
        kill()
        return
    transport, protocol = result
    controller = Controller(protocol)

    with tui.Tui(loop, controller) as utui:
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            pass #graceful exit

    if protocol.gui_exception:
        log.critical("Exception raised in GUI callback function:")
        kill()
        raise protocol.gui_exception

    log.debug("terminating")
    transport.close()
    pending = asyncio.Task.all_tasks()
    for task in pending: task.cancel()
    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    kill()

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