import subprocess, shlex, asyncio
import logging as log
from pluginmanager import Action
from plugins.pluginskel import SkeletonPlugin
from functools import partial
import concurrent.futures

## Friendly reminder ##
## This plugin is safe if-and-only-if the enduser is connected via an
## SSH tunnel, thereby proving it has the needed credentials.
## This plugin MUST NOT be used when a client is potentially unprivileged,
## such as with a http client. Or using a TCP socket instead of Unix socket.

MAX_TIME_SUBPROCESS = 3

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
        def shell(action):
            return subprocess.run(action, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        action = shlex.split("{}".format(lctx.argv[1]))
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        loop = self.gctx['loop']
        blocking_task = loop.run_in_executor(executor, shell, action)
        #try:
        out = await asyncio.wait_for(blocking_task, timeout=None)
        #except concurrent.futures._base.TimeoutError:
            #blocking_task.cancel()
            #try:
                #await blocking_task
            #except asyncio.CancelledError:
                #return "mine"
            #return "Subprocess took more than {} seconds. Killed.".format(MAX_TIME_SUBPROCESS)


        msg = {'stdout':str(out.stdout, encoding='utf-8'),
               'stderr':str(out.stderr, encoding='utf-8'),
               'returncode':str(out.returncode)}
        lctx.write_json(msg)

