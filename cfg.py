DEFAULTS = {
    'general': {
        "port":         4000,
        "address":      "localhost",
        #"address":      "", ##all
        "config":       "/etc/cncd.conf",
        "log_level":    "ERROR",
        "library":      "/var/lib/gcode",
    }
}

import logging as log

def parse_args(defaults):
    from argparse import ArgumentParser
    general = defaults['general']
    parser = ArgumentParser()
    parser.add_argument("-c", "--config", help="Alternative configuration file",
            action="store")
    parser.add_argument("-l", "--log-level",
            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            type=str.upper, action="store")
    args = parser.parse_args()

    ## prelimenary log level
    if args.log_level:
        level = getattr(log, args.log_level.upper())
    else:
        level = general["log_level"]
    log.getLogger().setLevel(level)

    return args

def print_config(cfg):
    log.debug("Using configuration:")
    for section in cfg.sections():
        log.debug("[{}]".format(section))
        for key, value in cfg[section].items():
            log.debug("  {} = {}".format(key, value))

def read_config(defaults, args):
    from configparser import ConfigParser
    cfg = ConfigParser()
    cfg.read_dict(defaults)

    ## Now, let anything in args overwrite defaults
    general = cfg['general']
    for arg in vars(args):
        value = getattr(args, arg)
        if value == None: continue
        log.debug("Overwriting default value for {} with {}".format(
                arg, value))
        general[arg] = str(value)

    log.info("Loading configuration file \"{}\"".format(general["config"]))
    if not cfg.read(general["config"]):
        log.error("Could not load any configuration file")

    if not args.log_level:
        ## apply verbosity
        level = getattr(log, general["log_level"].upper(), None)
        if not isinstance(level, int):
            raise ValueError('Invalid log level: %s' % level)
        rootlogger = log.getLogger()
        rootlogger.setLevel(level)

    print_config(cfg)
    return cfg

def load_configuration():
    global DEFAULTS
    args = parse_args(DEFAULTS)
    return read_config(DEFAULTS, args)

