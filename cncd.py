#!/usr/bin/env python3
import socketserver

DEFAULTS = {
    'general': {
        "port":         4000,
        "address":      "::",
        "config":         "/etc/cncd.conf",
        "verbose":         "No",
    }
}

def parse_args(defaults):
    from argparse import ArgumentParser
    general = defaults['general']
    parser = ArgumentParser()
    parser.add_argument("-c", "--config", help="Alternative configuration file",
            action="store")
    parser.add_argument("-v", "--verbose", help="Log messages to stdout",
            action="store_true")
    return parser.parse_args()

def print_config(cfg):
    print()
    for section in cfg.sections():
        print("[{}]".format(section))
        for key, value in cfg[section].items():
            print("{} = {}".format(key, value))

def read_config(defaults, args):
    from configparser import ConfigParser
    cfg = ConfigParser()
    cfg.read_dict(defaults)

    ## Now, let anything in args overwrite defaults
    general = cfg['general']
    for arg in vars(args):
        value = getattr(args, arg)
        if value == None: continue
        if args.verbose:
            print("Overwriting default value for {} ({}) with {}".format(
                    arg, general[arg], value))
        general[arg] = str(value)
    cfg.read(args.config)
    if cfg.getboolean("general", "verbose"):
        print_config(cfg)
    return cfg

args = parse_args(DEFAULTS)
cfg = read_config(DEFAULTS, args)




#while True:
    # handle running print jobs
    # handle current connections
    # handle new connections

#close incoming sock
#stop printing jobs
#disconnect printer
#disconnect users
