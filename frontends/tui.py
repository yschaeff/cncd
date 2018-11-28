#!/usr/bin/python3

import urwid
from urwid import Frame, Text, Filler, AttrMap, ListBox, Divider, SimpleFocusListWalker,\
    Button, WidgetWrap, Pile
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

class InputPile(urwid.WidgetWrap):
    def __init__(self, keypress, widget_list, focus_item=None):
        pile = Pile(widget_list, focus_item)
        urwid.WidgetWrap.__init__(self, pile)
        self.alt_keypress = keypress
    def keypress(self, size, key):
        if self.alt_keypress(size, key):
            return True
        else:
            return super().keypress(size, key)

class Tui():
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
            self.footer.set_text(f"Unhandled Key Press: {key}")
            return False
        return True

    def __enter__(self):
        self.mainloop.start()

    def __exit__(self, exceptiontype, exceptionvalue, traceback):
        """Restore terminal and allow exceptions"""
        #if exceptiontype:
        log.critical(f"{exceptiontype}")
        log.critical(f"{exceptionvalue}")
        log.critical(f"{traceback}")
        self.mainloop.stop()
        return False

    def error_filter(self, lines):
        errors = False
        for line in lines:
            if line.startswith("ERROR"):
                self.footer.set_text(f"server: {line.strip()}")
                errors = True
            else:
                yield line
        if not errors:
            self.footer.set_text(f"server: OK")

    def statframe(self, device):
        self.footer.set_text(f"")
        widgets = [Text(f"Select file to load on \"{device}\""), Divider()]
        walker = SimpleFocusListWalker(widgets)
        shortcuts = {}

        def devlist_cb(lines):
            for line in self.error_filter(lines):
                filename = line.strip()
                button = Button(filename)
                #urwid.connect_signal(button, 'click', button_cb, device)
                walker.append(AttrMap(button, None, focus_map='selected'))
            walker.set_focus(2)
        self.controller.get_filelist(devlist_cb, device)

        def keypress(size, key):
            if key not in shortcuts:
                return False ## not handled
            shortcuts[key]()
            return True ## handled

        body = InputPile(keypress, [ListBox(walker)])
        return baseframe(body, self.header, self.footer)

    def devframe(self, device):
        self.footer.set_text(f"")
        widgets = [Text(f"Selected device \"{device}\""), Divider()]
        walker = SimpleFocusListWalker(widgets)
        shortcuts = {}

        def cmd_cb(lines):
            ## this seems to do nothing but any errors will be displayed
            ## in the statusbar
            for line in self.error_filter(lines): pass

        button = Button("Connect")
        def button_cb(button, device):
            self.controller.connect(cmd_cb, device)
        urwid.connect_signal(button, 'click', button_cb, device)
        walker.append(AttrMap(button, None, focus_map='selected'))
        shortcuts['c'] = partial(button_cb, button, device)

        button = Button("Disconnect")
        def button_cb(button, device):
            self.controller.disconnect(cmd_cb, device)
        urwid.connect_signal(button, 'click', button_cb, device)
        walker.append(AttrMap(button, None, focus_map='selected'))
        shortcuts['d'] = partial(button_cb, button, device)

        button = Button("Start")
        def button_cb(button, device):
            self.controller.start(cmd_cb, device)
        urwid.connect_signal(button, 'click', button_cb, device)
        walker.append(AttrMap(button, None, focus_map='selected'))
        shortcuts['s'] = partial(button_cb, button, device)

        button = Button("Abort")
        def button_cb(button, device):
            self.controller.stop(cmd_cb, device)
        urwid.connect_signal(button, 'click', button_cb, device)
        walker.append(AttrMap(button, None, focus_map='selected'))
        shortcuts['a'] = partial(button_cb, button, device)

        button = Button("Load File")
        def button_cb(button, device):
            self.windowstack.append(self.mainloop.widget)
            self.mainloop.widget = self.statframe(device)
        urwid.connect_signal(button, 'click', button_cb, device)
        walker.append(AttrMap(button, None, focus_map='selected'))
        shortcuts['l'] = partial(button_cb, button, device)

        def keypress(size, key):
            if key not in shortcuts:
                return False ## not handled
            shortcuts[key]()
            return True ## handled

        body = InputPile(keypress, [ListBox(walker)])
        return baseframe(body, self.header, self.footer)

    def devlistframe(self):
        """ Displays a list of available devices."""
        self.footer.set_text(f"")
        widgets = [Text("Available CNC Devices"), Divider()]
        walker = SimpleFocusListWalker(widgets)
        def devlist_cb(lines):
            def button_cb(button, device):
                ## go to device view
                self.windowstack.append(self.mainloop.widget)
                self.mainloop.widget = self.devframe(device)
            for line in lines:
                device = line.strip()
                button = Button(device)
                urwid.connect_signal(button, 'click', button_cb, device)
                walker.append(AttrMap(button, None, focus_map='selected'))
        self.controller.get_devlist(devlist_cb)
        body = ListBox(walker)
        return baseframe(body, self.header, self.footer)

