## this package is not available on regular debian, only rasbian
import RPi.GPIO as GPIO
import asyncio
import time

import logging as log
from collections import defaultdict
from functools import partial
from plugins.pluginskel import SkeletonPlugin
from pluginmanager import Action
from cncd import command

class Plugin(SkeletonPlugin):

    PLUGIN_API_VERSION = 1
    NAME = "Raspberry Pi GPIO plugin"
    HANDLES = ['gpio-get', 'gpio-set']
    ACTIONS = []

    def __init__(self, datastore, gctx:dict):
        super().__init__(datastore, gctx)
        cfg = self.gctx['cfg']
        self.fs_at_close = []
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
            try:
                self.setup(label, mode, int(pin), txt, action, edge, pud, export)
            except ValueError as e:
                log.error(f"Setup failed for pin {label} ({pin}): {e}")


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

            if edge != '':
                if edge == 'rising':
                    trig = GPIO.RISING
                elif edge == 'falling':
                    trig = GPIO.FALLING
                else:
                    trig = GPIO.BOTH
                def edge_detect(action, pin):
                    """ This can be triggered by EMF, therefore not only
                        debounce button jitter but also require long press
                    """
                    pre = GPIO.input(pin)
                    if (edge == 'rising' and not pre) or (edge == 'falling' and pre):
                        log.warning("GPIO spurious event. Ignoring.")
                        return
                    time.sleep(0.05) ## This is outside async loop, thus okay.
                    post = GPIO.input(pin)
                    if pre != post:
                        log.info("GPIO event stopped by debounce filter")
                        return

                    ## problem: this now runs in a different OS thread
                    ## therefore make sure we use the correct loop.
                    def do(action):
                        command(action, self.gctx, loopback=True)
                    loop = self.gctx['loop']
                    loop.call_soon_threadsafe(partial(do, action))
                GPIO.add_event_detect(pin, trig, partial(edge_detect, action), bouncetime=500)
                self.fs_at_close.append(partial(GPIO.remove_event_detect, pin))

        if export:
            self.ACTIONS.append(Action("gpio-set {} 1".format(pin), "{} on".format(label), txt))
            self.ACTIONS.append(Action("gpio-set {} 0".format(pin), "{} off".format(label), txt))


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
        for f in self.fs_at_close:
            f()
        GPIO.cleanup()


