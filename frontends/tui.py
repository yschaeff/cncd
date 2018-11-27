#!/usr/bin/python3

import urwid
from urwid import Frame, Text, Filler, AttrMap, ListBox, Divider, SimpleFocusListWalker,\
    Button
from functools import partial
import logging as log

palette = [('status', 'white,bold', 'dark blue')]

def baseframe(body, header, footer):
    return Frame(body,
            AttrMap(header, 'status'),
            AttrMap(footer, 'status'), 'body')

def initframe(header, footer):
    body = Filler(Text('Waiting for device list.'), 'top')
    return baseframe(body, header, footer)

def devlistframe(header, footer):
    def cb(button, device):
        ## go to device view
        pass
    body = [Text("Available CNC Devices"), Divider()]
    devices = []#["a", "b", "c"]
    for device in devices:
        button = Button(device)
        urwid.connect_signal(button, 'click', cb, device)
        body.append(AttrMap(button, None, focus_map='reversed'))
    walker = SimpleFocusListWalker(body)
    box = ListBox(walker)
    return baseframe(box, header, footer)

class Tui():
    def __init__(self, asyncio_loop):
        self.header = Text("Show help here.")
        self.footer = Text("status")
        #window = initframe(self.header, self.footer)
        window = devlistframe(self.header, self.footer)

        self.asyncio_loop = asyncio_loop
        evl = urwid.AsyncioEventLoop(loop=asyncio_loop)
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
