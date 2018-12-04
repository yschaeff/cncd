#!/usr/bin/python3

import urwid
from urwid import Frame, Text, Filler, AttrMap, ListBox, Divider, SimpleFocusListWalker,\
    Button, WidgetWrap, Pile, ExitMainLoop
from functools import partial
import logging as log

palette = [('status', 'white,bold', 'dark blue'), \
        ('selected', 'black', 'white')]

class Window(urwid.WidgetWrap):
    def __init__(self, tui):
        self.tui = tui
        self.header_str = "Q:quit q:previous"
        self.header = Text(self.header_str)
        self.body = Pile([])
        self.footer = Text("placeholder")
        self.frame = Frame(self.body,
            AttrMap(self.header, 'status'), AttrMap(self.footer, 'status'), 'body')
        urwid.WidgetWrap.__init__(self, self.frame)
        self.hotkeys = {} ## key:func
        self.add_hotkey('u', self.update, "update")

    def update(self):
        """Fetch new information and update labels, overwrite me"""
        pass

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

    def add_hotkey(self, key, func, label):
        self.hotkeys[key] = func
        self.header_str += f" {key}:{label}"
        self.header.set_text(self.header_str)

    def keypress(self, size, key):
        if key in self.hotkeys:
            self.hotkeys[key]()
            return True
        else:
            return super().keypress(size, key)

class FileListWindow(Window):
    def __init__(self, tui, device):
        super().__init__(tui)
        self.body.contents.append((Text("Select file to load on \"{device}\""), ('pack', None)))
        self.body.contents.append((Divider(), ('pack', None)))

        walker = SimpleFocusListWalker([])
        listbox = ListBox(walker)
        self.body.contents.append((listbox, ('weight', 1)))
        self.body.focus_position = 2
        def load_cb(lines):
            for line in self.error_filter(lines): pass
            tui.pop_window()

        def button_cb(device, filename, button):
            tui.controller.load(load_cb, device, filename)

        def devlist_cb(lines):
            for line in self.error_filter(lines):
                filename = line.strip()
                button = Button(filename)
                urwid.connect_signal(button, 'click', button_cb, user_args=[device, filename])
                walker.append(AttrMap(button, None, focus_map='selected'))
        tui.controller.get_filelist(devlist_cb, device)

class DeviceWindow(Window):
    def __init__(self, tui, locator, device):
        super().__init__(tui)
        self.body.contents.append((Text(f"Selected device \"{device}\""), ('pack', None)))
        self.body.contents.append((Divider(), ('pack', None)))

        walker = SimpleFocusListWalker([])
        listbox = ListBox(walker)
        self.body.contents.append((listbox, ('weight', 1)))
        self.body.focus_position = 2

        def cmd_cb(lines):
            for line in self.error_filter(lines): pass

        button = Button("Connect")
        def button_cb(button, locator):
            tui.controller.connect(cmd_cb, locator)
        urwid.connect_signal(button, 'click', button_cb, locator)
        walker.append(AttrMap(button, None, focus_map='selected'))
        self.add_hotkey('c', partial(button_cb, button, locator), "connect")

        button = Button("Disconnect")
        def button_cb(button, locator):
            tui.controller.disconnect(cmd_cb, locator)
        urwid.connect_signal(button, 'click', button_cb, locator)
        walker.append(AttrMap(button, None, focus_map='selected'))
        self.add_hotkey('d', partial(button_cb, button, locator), "disconnect")

        button = Button("Start")
        def button_cb(button, locator):
            tui.controller.start(cmd_cb, locator)
        urwid.connect_signal(button, 'click', button_cb, locator)
        walker.append(AttrMap(button, None, focus_map='selected'))
        self.add_hotkey('s', partial(button_cb, button, locator), "start")

        button = Button("Abort")
        def button_cb(button, locator):
            tui.controller.stop(cmd_cb, locator)
        urwid.connect_signal(button, 'click', button_cb, locator)
        walker.append(AttrMap(button, None, focus_map='selected'))
        self.add_hotkey('a', partial(button_cb, button, locator), "abort")

        button = Button("Load File")
        def button_cb(button, locator):
            window = FileListWindow(tui, locator)
            tui.push_window(window)
        urwid.connect_signal(button, 'click', button_cb, locator)
        walker.append(AttrMap(button, None, focus_map='selected'))
        self.add_hotkey('l', partial(button_cb, button, locator), "load")

class DeviceListWindow(Window):
    def __init__(self, tui):
        super().__init__(tui)
        self.body.contents.append((Text("Available CNC Devices"), ('pack', None)))
        self.body.contents.append((Divider(), ('pack', None)))

        walker = SimpleFocusListWalker([])
        listbox = ListBox(walker)
        self.body.contents.append((listbox, ('weight', 1)))
        self.body.focus_position = 2
        def devlist_cb(devices):
            def button_cb(locator, device, button):
                window = DeviceWindow(tui, locator, device)
                tui.push_window(window)
            for locator, device in devices:
                button = Button(device)
                urwid.connect_signal(button, 'click', button_cb, user_args=[locator, device])
                walker.append(AttrMap(button, None, focus_map='selected'))
        self.tui.controller.get_devlist(devlist_cb)

class Tui():
    def set_header_text(self, txt):
        self.header.set_text("Q:quit! q:back"+txt)
    def __init__(self, asyncio_loop, controller):
        urwid.command_map['j'] = 'cursor down'
        urwid.command_map['k'] = 'cursor up'
        self.controller = controller
        self.header = Text("")
        self.set_header_text("")
        self.footer = Text("status")
        self.windowstack = []

        self.asyncio_loop = asyncio_loop
        evl = urwid.AsyncioEventLoop(loop=asyncio_loop)
        window = DeviceListWindow(self)
        self.mainloop = urwid.MainLoop(window, palette,
                unhandled_input=self._unhandled_input, event_loop=evl)

    def push_window(self, window):
        self.windowstack.append(self.mainloop.widget)
        self.mainloop.widget = window

    def pop_window(self):
        if self.windowstack:
            window = self.windowstack.pop()
            window.update()
            self.mainloop.widget = window

    def _unhandled_input(self, key):
        if key == 'q':
            self.pop_window()
        if key == 'Q':
            self.asyncio_loop.stop()
        else:
            self.footer.set_text(f"Unhandled Key Press: {key}")
            return False
        return True

    def __enter__(self):
        self.mainloop.start()

    def __exit__(self, exceptiontype, exceptionvalue, traceback):
        """Restore terminal and allow exceptions"""
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
