## this package is not available on regular debian, only rasbian
import RPi.GPIO as GPIO

import logging as log
from collections import defaultdict
from plugins.pluginskel import SkeletonPlugin
from pluginmanager import Action

class Plugin(SkeletonPlugin):

    PLUGIN_API_VERSION = 1
    NAME = "Raspberry Pi GPIO plugin"
    HANDLES = ['gpio']
    ACTIONS = []

    def __init__(self, datastore, gctx:dict):
        self.gctx = gctx
        cfg = self.gctx['cfg']
        if 'gpio' in cfg:
            cfg_gpio = cfg['gpio']
        else:
            cfg_gpio = defaultdict(str)
        if cfg_gpio.get('moder') == 'bcm':
            GPIO.setmode(GPIO.BCM)
        else:
            GPIO.setmode(GPIO.BOARD)
        GPIO.setwarnings(False);
        ## actions
        pinstr = cfg_gpio['pins']
        pin_sections = [pin.strip() for pin in pinstr.split(',')]
        for section in pin_sections:
            if section not in cfg:
                log.warning("Can't find config section for '{}'".format(section))
                continue
            label = cfg[section].get('label', 'ACTION')
            mode = cfg[section].get('mode', 'output')
            pin = cfg[section].get('pin',0)
            txt = cfg[section].get('description', 'NOTSET')
            self.ACTIONS.append(Action("gpio {} 0".format(pin), "{} off".format(label), txt))
            self.ACTIONS.append(Action("gpio {} 1".format(pin), "{} on".format(label), txt))

    async def handle_command(self, gctx:dict, cctx:dict, lctx) -> None:
        argv = lctx.argv
        if len(argv) < 2:
            lctx.writeln("ERROR Must specify pin and state or pin")
            return
        try:
            pin = int(argv[1])
        except ValueError:
            lctx.writeln("ERROR Can't parse pin number")
            return
        if len(argv) < 3:
            try:
                GPIO.setup(pin, GPIO.IN)
                state = GPIO.input(pin)
                lctx.writeln("{}:{}".format(pin, state))
            except ValueError:
                lctx.writeln("invalid pin number")
            return
        try:
            value = int(argv[2])
        except ValueError:
            lctx.writeln("ERROR Can't parse value")
            return
        state = [GPIO.HIGH, GPIO.LOW][not value]
        try:
            GPIO.setup(pin, GPIO.OUT, initial=state)
        except ValueError:
            lctx.writeln("invalid pin number")

    def close(self) -> None:
        GPIO.cleanup()


