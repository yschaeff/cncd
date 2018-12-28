import subprocess, shlex
import logging as log
from pluginmanager import Action
from plugins.pluginskel import SkeletonPlugin

class Plugin(SkeletonPlugin):
    """Inherit from this class for all Plugins"""
    NAME = "shell"
    PLUGIN_API_VERSION = 0
    HANDLES = ["shell"] #of type string
    ACTIONS = []

    def __init__(self, datastore, gctx:dict):
        cfg = gctx['cfg']
        if 'shell' in cfg:
            cfg_shell = cfg['shell']
        else:
            cfg_shell = defaultdict(str)
        for key, value in cfg_shell.items():
            self.ACTIONS.append(Action("shell {}".format(shlex.quote(value)), key, "??"))

    async def handle_command(self, gctx, cctx, lctx):
        if len(lctx.argv) != 2:
            lctx.writeln("ERROR specify 1 command exactly")
            return
        out = subprocess.Popen(shlex.split("{}".format(lctx.argv[1])))

