import logging as log
import plugins.pluginskel

## todo seperate logger for this plugin

## we need a plugin manager, which guards the plugins with try: except:
## it will make sure async can do it's work
## unload misbehavinf plugins

class Plugin(plugins.pluginskel.SkeletonPlugin):
    
    def handles_command(self, cmd):
        if cmd == 'xxx':
            log.info("handled")
            return True
        log.info("NOT handled")
        return False

    def handle_command(self, argv, gctx, cctx, lctx):
        """must return iterable, each item will be written to connection
           as new line"""
        if argv[0] == 'xxx':
            for i in range(1000000):
                yield "hi {}!".format(i)
