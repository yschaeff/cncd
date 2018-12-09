import logging as log

class PluginManager():
    def __init__(self, gctx):
        self.gctx = gctx


    def load_plugins(self):
        general = self.gctx['cfg']["general"]
        plugin_path = general["plugin_path"]
        plugins_enabled = general["plugins_enabled"]
        self.gctx["plugins"] = []
        import importlib.util

        names = plugins_enabled.split(',')
        paths = ["{}/{}.py".format(plugin_path, name) for name in names]
        for path in paths:
            spec = importlib.util.spec_from_file_location("module.name", path)
            plugin = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(plugin)
            log.info("Loading plugin {}".format(path))
            try:
                instance = plugin.Plugin()
            except Exception as e:
                log.error("Plugin crashed during loading. Not activated.")
                log.error(traceback.format_exc())
                continue
            self.gctx["plugins"].append(instance)

    def unload_plugins(self):
        for plugin in self.gctx["plugins"]:
            try:
                plugin.close()
            except Exception as e:
                log.error("Plugin crashed during unloading")
                log.error(traceback.format_exc())
        self.gctx["plugins"] = []


