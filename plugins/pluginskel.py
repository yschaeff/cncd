import logging as log

class SkeletonPlugin():
    def __init__(self):
        pass

    def handles_command(self, cmd):
        return False

    def handle_command(self, argv, gctx, cctx, lctx):
        """must return iterable, each item will be written to connection
           as new line"""
        if argv == 'skeleton':
            yield "This is not a real plugin, Don't load me."

    def close(self):
        pass

