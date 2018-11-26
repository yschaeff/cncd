#!/usr/bin/python3

import asyncio, concurrent
import urwid
from urwid import Frame, Text, Filler, AttrMap
from functools import partial
import logging as log

palette = [('status', 'white,bold', 'dark blue')]

def baseframe(body, header, footer):
    return Frame(body,
            AttrMap(header, 'status'),
            AttrMap(footer, 'status'), 'body')

class Tui():
    def __init__(self, asyncio_loop):
        self.header = Text("Show help here.")
        self.footer = Text("status")
        txt = Filler(Text('Waiting for device list.'), 'top')
        window = baseframe(txt, self.header, self.footer)

        self.asyncio_loop = asyncio_loop
        evl = urwid.AsyncioEventLoop(loop=asyncio.get_event_loop())
        self.mainloop = urwid.MainLoop(window, palette, unhandled_input=self._unhandled_input, event_loop=evl)
    def _unhandled_input(self, key):
        if key == 'q':
            self.asyncio_loop.stop()
        else:
            self.footer.set_text(f"Pressed key: {key}")
            return False
        return True
    def __enter__(self):
        self.mainloop.start()
    def __exit__(self, exceptiontype, exceptionvalue, traceback):
        """Restore terminal and allow exceptions"""
        self.mainloop.stop()
        return False

def main(loop):
    with Tui(loop) as tui:
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            pass
    log.debug("terminating")
    pending = asyncio.Task.all_tasks()
    for task in pending: task.cancel()
    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

if __name__ == '__main__':
    log.basicConfig(level=log.DEBUG)
    loop = asyncio.get_event_loop()
    main(loop)
    loop.close()
