import logging as log

class GenericFirmware:
    def __init__(self):
        self.prompt             = ""
        self.max_buffer_lenght  = 1
        self.stop_gcodes        = ['M104 S0', 'M140 S0']
        self.abort_gcodes       = ['M112']

    def is_ack(self, line):
        return line.startswith('ok')

    def is_error(self, line):
        return line.startswith('!!')

    def set_next_linenumber(self, n:int):
        """after sending this gcode the printer should expect line n"""
        return "M110 N{}".format(n)

    def strip_prompt(self, line):
        if self.prompt and line.startswith(self.prompt):
            return line[len(self.prompt):]
        else:
            return line

class MarlinFirmware(GenericFirmware):
    def __init__(self):
        super().__init__()
        self.prompt = ""

    def is_error(self, line):
        return line.startswith('ERROR:')

class SmoothieFirmware(GenericFirmware):
    ## ONLY TESTED CONNECTED TO TELNET FOR SERIAL SETTINGS MAY DIFFER
    def __init__(self):
        super().__init__()
        self.prompt = "> "
        self.max_buffer_lenght = 20

    def set_next_linenumber(self, n:int):
        return "N{} M110".format(n)


def get_firmware(name):
    if name == "marlin":
        FW = MarlinFirmware
    elif name == "smoothie":
        FW = SmoothieFirmware
    elif name == "generic":
        FW = GenericFirmware
    else:
        log.warning("Firmware dialect ({}) not known, defaulting to generic.")
        FW = GenericFirmware
    return FW()

