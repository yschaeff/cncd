import subprocess, shlex
import logging as log
from pluginmanager import Action
from plugins.pluginskel import SkeletonPlugin

## Friendly reminder ##
## This plugin is safe if-and-only-if the enduser is connected via an
## SSH tunnel, thereby proving it has the needed credentials.
## This plugin MUST NOT be used when a client is potentially unprivileged,
## such as with a http client. Or using a TCP socket instead of Unix socket.

class Plugin(SkeletonPlugin):
    """Inherit from this class for all Plugins"""
    NAME = "shell"
    PLUGIN_API_VERSION = 0
    HANDLES = ["shell"] #of type string
    ACTIONS = []

    def __init__(self, datastore, gctx:dict):
        super().__init__(datastore, gctx)
        cfg = gctx['cfg']
        if 'shell' in cfg:
            cfg_shell = cfg['shell']
        else:
            cfg_shell = defaultdict(str)
        for key, value in cfg_shell.items():
            quoted = shlex.quote(value)
            self.ACTIONS.append(Action("shell {}".format(quoted), key, "({})".format(value)))

    async def handle_command(self, gctx, cctx, lctx):
        if len(lctx.argv) != 2:
            return "specify 1 command exactly"
        out = subprocess.run(shlex.split("{}".format(lctx.argv[1])),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        msg = {'stdout':str(out.stdout, encoding='utf-8'),
               'stderr':str(out.stderr, encoding='utf-8'),
               'returncode':str(out.returncode)}
        lctx.write_json(msg)

