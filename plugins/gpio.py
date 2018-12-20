import logging as log
from plugins.pluginskel import SkeletonPlugin
## this package is not available on regular debian
import RPi.GPIO as GPIO

class Plugin(SkeletonPlugin):

    PLUGIN_API_VERSION = 1
    NAME = "Raspberry Pi GPIO plugin"
    PREHOOKS = {}
    POSTHOOKS = {}
    HANDLES = ['gpio']

    def __init__(self, datastore, gctx:dict):
        self.gctx = gctx
        GPIO.setwarnings(False);
        GPIO.setmode(GPIO.BOARD)

    def handle_command(self, gctx:dict, cctx:dict, lctx) -> None:
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


