import logging as log
from pluginmanager import Action
from plugins.pluginskel import SkeletonPlugin
from collections import defaultdict

class Plugin(SkeletonPlugin):
    NAME = "Action"
    PLUGIN_API_VERSION = 0
    HANDLES = ["actions"] #of type string
    ACTIONS = [] #of type Action

    def __init__(self, datastore, gctx:dict):
        super().__init__(datastore, gctx)
        cfg = gctx['cfg']
        if 'actions' in cfg:
            cfg_actions = cfg['actions']
        else:
            cfg_actions = defaultdict(str)
        for key, value in cfg_actions.items():
            self.ACTIONS.append(Action(value, key, "({})".format(value)))


    async def handle_command(self, gctx, cctx, lctx):
        pluginmanager = gctx['pluginmanager']
        actions = pluginmanager.get_actions()
        msg = []
        for cmd, short, long in actions:
            msg.append({"command":cmd, "short":short, "long":long})
        lctx.write_json({'actions':msg})

