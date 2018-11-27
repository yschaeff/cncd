#!/usr/bin/python3

import urwid
from urwid import Frame, Text, Filler, AttrMap, ListBox, Divider, SimpleFocusListWalker,\
    Button
from functools import partial
import logging as log

palette = [('status', 'white,bold', 'dark blue'), \
        ('selected', 'black', 'white')]

def baseframe(body, header, footer):
    return Frame(body,
        AttrMap(header, 'status'),
        AttrMap(footer, 'status'), 'body')

def initframe(header, footer):
    body = Filler(Text('Waiting for device list.'), 'top')
    return baseframe(body, header, footer)

class Tui():
    def devframe(self, device):
        def button_cb(button, device):
            ## go to device view
            self.windowstack.append(self.mainloop.widget)
            self.mainloop.widget = initframe(self.header, self.footer)
        body = [Text(f"Selected device \"{device}\""), Divider()]
        walker = SimpleFocusListWalker(body)
        def devlist_cb(lines):
            for line in lines:
                device = line.strip()
                button = Button(device)
                #urwid.connect_signal(button, 'click', button_cb, device)
                walker.append(AttrMap(button, None, focus_map='selected'))
        self.controller.get_status(devlist_cb, device)
        button = Button("File selected:")
        walker.append(button)
        box = ListBox(walker)
        return baseframe(box, self.header, self.footer)

    def devlistframe(self):
        def button_cb(button, device):
            ## go to device view
            self.windowstack.append(self.mainloop.widget)
            self.mainloop.widget = self.devframe(device)
        body = [Text("Available CNC Devices"), Divider()]
        walker = SimpleFocusListWalker(body)
        def devlist_cb(lines):
            for line in lines:
                device = line.strip()
                button = Button(device)
                urwid.connect_signal(button, 'click', button_cb, device)
                walker.append(AttrMap(button, None, focus_map='selected'))
        self.controller.get_devlist(devlist_cb)
        box = ListBox(walker)
        return baseframe(box, self.header, self.footer)

    def __init__(self, asyncio_loop, controller):
        urwid.command_map['j'] = 'cursor down'
        urwid.command_map['k'] = 'cursor up'
        self.controller = controller
        self.header = Text("q:quit bcksp:prev")
        self.footer = Text("status")
        window = self.devlistframe()
        self.windowstack = []

        self.asyncio_loop = asyncio_loop
        evl = urwid.AsyncioEventLoop(loop=asyncio_loop)
        self.mainloop = urwid.MainLoop(window, palette,
                unhandled_input=self._unhandled_input, event_loop=evl)

    def _unhandled_input(self, key):
        if key == 'q':
            if self.windowstack:
                frame = self.windowstack.pop()
                self.mainloop.widget = frame
            else:
                self.asyncio_loop.stop()
        elif key == 'Q':
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
