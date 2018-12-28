## this package is not available on regular debian, only rasbian
import RPi.GPIO as GPIO
import asyncio

import logging as log
from collections import defaultdict
from plugins.pluginskel import SkeletonPlugin
from pluginmanager import Action
from cncd import SocketHandler

class Plugin(SkeletonPlugin):

    PLUGIN_API_VERSION = 1
    NAME = "Raspberry Pi GPIO plugin"
    HANDLES = ['gpio-get', 'gpio-set']
    ACTIONS = []

    def __init__(self, datastore, gctx:dict):
        self.gctx = gctx
        cfg = self.gctx['cfg']
        if 'gpio' in cfg:
            cfg_gpio = cfg['gpio']
        else:
            cfg_gpio = defaultdict(str)
        if cfg_gpio.get('mode') == 'bcm':
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
            action = cfg[section].get('action', '')
            edge = cfg[section].get('edge', '')
            pud = cfg[section].get('pud', '')
            export = cfg[section].get('export', '')
            self.setup(label, mode, int(pin), txt, action, edge, pud, export)

    def setup(self, label, mode, pin, txt, action, edge, pud, export):
        if mode == 'output':
            GPIO.setup(pin, GPIO.OUT)
        elif mode == 'pwm':
            pass ## not IMPL
        else:
            if pud == 'down':
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            elif pud == 'up':
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            else:
                GPIO.setup(pin, GPIO.IN)

            if edge:
                if edge == 'rising':
                    trig = GPIO.RISING
                elif edge == 'falling':
                    trig = GPIO.FALLING
                else:
                    trig = GPIO.BOTH
                def edge_detect(pin, action):
                    async def do(action):
                        s = SocketHandler(self.gctx, loopback=True)
                        s.command(action)
                    task = asyncio.ensure_future(do(action))
                GPIO.add_event_detect(pin, trig, edge_detect, bouncetime=200)
                ## todo: abort tasks on close()

        if export:
            self.ACTIONS.append(Action("gpio-set {} 0".format(pin), "{} off".format(label), txt))
            self.ACTIONS.append(Action("gpio-set {} 1".format(pin), "{} on".format(label), txt))


    def gpio_set(self, argv):
        try:
            pin = int(argv[0])
            state = int(argv[1])
            if state == -1: ##toggle
                state = not GPIO.input(pin)
            GPIO.setup(pin, GPIO.OUT, initial=state)
        except IndexError:
            lctx.writeln("ERROR Must supply pin and state")
        except ValueError:
            lctx.writeln("ERROR invalid pin number")

    def gpio_get(self, argv):
        try:
            pin = int(argv[0])
            GPIO.setup(pin, GPIO.IN)
            state = GPIO.input(pin)
            lctx.writeln("{}:{}".format(pin, state))
        except IndexError:
            lctx.writeln("ERROR Must supply pin")
        except ValueError:
            lctx.writeln("ERROR invalid pin number")

    async def handle_command(self, gctx:dict, cctx:dict, lctx) -> None:
        if lctx.argv[0] == 'gpio-set':
            self.gpio_set(lctx.argv[1:])
        elif lctx.argv[1] == 'gpio-get':
            self.gpio_get(lctx.argv[1:])

    def close(self) -> None:
        GPIO.cleanup()


