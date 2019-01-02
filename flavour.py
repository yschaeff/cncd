import logging as log

class GenericFirmware:
    max_buffer_lenght = 1
    checksums = True
    
    def set_next_linenumber(self, n:int):
        """after sending this gcode the printer should expect line n"""
        return "M110 N{}".format(n)
    def strip_prompt(self, line):
        if self.prompt and line.startswith(self.prompt):
            return line[len(prompt):]
        else:
            return line

class MarlinFirmware(GenericFirmware):
    prompt = ""

class SmoothieFirmware(GenericFirmware):
    prompt = "> "
    max_buffer_lenght = 10
    ## disable checksumming for this device because it will add .5 seconds
    ## delay!
    checksums = False
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
    

