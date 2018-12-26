import logging as log
import functools
import traceback
from collections import defaultdict, namedtuple

Callback = namedtuple('Callback', 'plugin callback')
Action = namedtuple("Action", "command short_descr long_descr")

pluginmanager = None

def plugin_hook(func):
    """ This is a decorator that enables plugins to hook in to this functions"""
    global pluginmanager
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        qname = func.__qualname__
        module = func.__module__
        prehooks, posthooks = pluginmanager.hooks_for(module, qname)
        for hook in prehooks:
            if not hook.callback: continue
            log.debug("Function {} was pre hooked by {}".format(qname, hook.plugin.NAME))
            try:
                await hook.callback(*args, **kwargs)
            except Exception as e:
                log.error("plugin '{}' crashed.".format(hook.plugin.NAME))
                log.error(traceback.format_exc())
                pluginmanager.disable_bad_plugin(hook.plugin)
        else:
            log.debug("No hook registered for {} {}".format(module, qname))
        r = await func(*args, **kwargs)
        for hook in posthooks:
            if not hook.callback: continue
            log.debug("Function {} was post hooked by {}".format(qname, hook.plugin.NAME))
            try:
                await hook.callback(*args, **kwargs)
            except Exception as e:
                log.error("plugin '{}' crashed.".format(hook.plugin.NAME))
                log.error(traceback.format_exc())
                pluginmanager.disable_bad_plugin(hook.plugin)
        else:
            log.debug("No hook registered for {} {}".format(module, qname))
        return r
    return wrapper

class PluginManager():
    def __init__(self, gctx):
        global pluginmanager
        pluginmanager = self
        self.gctx = gctx
        self.prehooks = defaultdict(list)
        self.posthooks = defaultdict(list)
        self.store = gctx['datastore']

    def hooks_for(self, module, qname):
        return self.prehooks[(module, qname)], self.posthooks[(module, qname)]

    def get_handlers(self):
        for plugin in self.gctx["plugins"]:
            for handle in plugin.HANDLES:
                yield handle, plugin.handle_command

    def get_actions(self):
        for plugin in self.gctx["plugins"]:
            for action in plugin.ACTIONS:
                yield action

    def collect_hooks(self, instance):
        for target, callbacks in instance.PREHOOKS.items():
            hooks = [Callback(instance, callback) for callback in callbacks]
            self.prehooks[target].extend(hooks)
        for target, callbacks in instance.POSTHOOKS.items():
            hooks = [Callback(instance, callback) for callback in callbacks]
            self.posthooks[target].extend(hooks)

    def disable_bad_plugin(self, plugin):
        if plugin not in self.gctx["plugins"]:
            return
        log.error("Misbehaving plugin '{}' unloaded.".format(plugin.NAME))
        self.gctx["plugins"].remove(plugin)
        try:
            plugin.close()
        except Exception as e:
            log.error("Plugin crashed during unloading")
            log.error(traceback.format_exc())

        for target, hooks in self.prehooks.items():
            badhooks = [hook for hook in hooks if hook.plugin == plugin]
            for hook in badhooks:
                hooks.remove(hook)
        for target, hooks in self.posthooks.items():
            badhooks = [hook for hook in hooks if hook.plugin == plugin]
            for hook in badhooks:
                hooks.remove(hook)

    def load_plugins(self):
        general = self.gctx['cfg']["general"]
        plugin_path = general["plugin_path"]
        plugins_enabled = general["plugins_enabled"]
        self.gctx["plugins"] = []
        import importlib.util

        names = [name.strip() for name in plugins_enabled.split(',')]
        paths = ["{}/{}.py".format(plugin_path, name) for name in names]
        for path in paths:
            spec = importlib.util.spec_from_file_location("module.name", path)
            plugin = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(plugin)
            except FileNotFoundError:
                log.error("Plugin \"{}\" not found. Not activated.".format(path))
                continue
            except ModuleNotFoundError as e:
                log.error("Plugin dependency not found: {}".format(e))
                continue
            log.info("Loading plugin {}".format(path))
            try:
                instance = plugin.Plugin(self.store, self.gctx)
            except Exception as e:
                log.error("Plugin crashed during loading. Not activated.")
                log.error(traceback.format_exc())
                continue
            self.gctx["plugins"].append(instance)
            self.collect_hooks(instance)

    def unload_plugins(self):
        for plugin in self.gctx["plugins"]:
            try:
                plugin.close()
            except Exception as e:
                log.error("Plugin crashed during unloading")
                log.error(traceback.format_exc())
        self.gctx["plugins"] = []


