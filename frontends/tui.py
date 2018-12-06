#!/usr/bin/python3

import urwid
from urwid import Frame, Text, Filler, AttrMap, ListBox, Divider, SimpleFocusListWalker,\
    Button, WidgetWrap, Pile, ExitMainLoop, Columns, Edit, Padding, BoxAdapter
from functools import partial
import logging as log
import re
import webbrowser

palette = [('status', 'white,bold', 'dark blue'), \
        ('selected', 'black', 'white')]

class Window(urwid.WidgetWrap):
    def __init__(self, tui):
        self.tui = tui
        self.header_str = "Q:quit q:previous L:log"
        self.header = Text(self.header_str)
        self.body = Pile([])
        self.footer = Text("placeholder")
        self.frame = Frame(self.body,
            AttrMap(self.header, 'status'), AttrMap(self.footer, 'status'), 'body')
        urwid.WidgetWrap.__init__(self, self.frame)
        self.hotkeys = {} ## key:func

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
        if key not in self.hotkeys:
            self.hotkeys[key] = func
            self.header_str += f" {key}:{label}"
            self.header.set_text(self.header_str)

    def keypress(self, size, key):
        if key in self.hotkeys:
            self.hotkeys[key]()
            return True
        else:
            return super().keypress(size, key)

class LogWindow(Window):
    def __init__(self, tui):
        super().__init__(tui)
        self.body.contents.append((Text(f"LOG"), ('pack', None)))
        self.body.contents.append((Divider(), ('pack', None)))

class CB_Edit(Edit):
    def __init__(self, caption, edit_text, type_cb, enter_cb):
        super().__init__(caption, edit_text)
        self.type_cb = type_cb
        self.enter_cb = enter_cb
    def keypress(self, size, key):
        handled = super().keypress(size, key)
        self.type_cb(self.get_edit_text())
        if key == 'enter':
            self.enter_cb()
            return True
        return handled


class FileListWindow(Window):
    def __init__(self, tui, locator, device):
        super().__init__(tui)
        self.body.contents.append((Text(f"Select file to load on \"{device}\""), ('pack', None)))
        self.body.contents.append((Divider(), ('pack', None)))
        self.device = device

        self.locator = locator
        self.device = device

        def limit(regexp):
            self.regexp = regexp
            self.populate_list()
        def enter():
            if len(self.walker) < 1:
                self.tui.pop_window()
                return
            button = self.walker[0]
            button.keypress(1, 'enter')

        editbox = CB_Edit("Limit (regexp): ", "", limit, enter)
        self.body.contents.append((editbox, ('pack', 1)))
        self.body.contents.append((Divider(), ('pack', 1)))

        self.walker = SimpleFocusListWalker([])
        listbox = ListBox(self.walker)
        self.body.contents.append((listbox, ('weight', 1)))
        self.body.focus_position = 2
        self.update()
        self.regexp = ".*"

    def populate_list(self):
        self.walker.clear()
        try:
            p = re.compile(self.regexp, re.IGNORECASE)
        except re.error:
            filtered_files = self.all_files
        else:
            filtered_files = filter(p.search, self.all_files)

        def load_cb(lines):
            for line in self.error_filter(lines): pass
            self.tui.pop_window()
        def button_cb(device, filename, button):
            self.tui.controller.load(load_cb, self.locator, filename)
        self.walker.clear()
        for line in filtered_files:
            filename = line.strip()
            button = Button(filename)
            urwid.connect_signal(button, 'click', button_cb, user_args=[self.device, filename])
            self.walker.append(AttrMap(button, None, focus_map='selected'))

    def update(self):
        def devlist_cb(lines):
            self.all_files = [line for line in self.error_filter(lines)]
            self.populate_list()
        self.tui.controller.get_filelist(devlist_cb, self.locator)

class DeviceWindow(Window):
    def __init__(self, tui, locator, device):
        super().__init__(tui)
        self.body.contents.append((Text(f"Selected device \"{device}\""), ('pack', None)))
        self.body.contents.append((Divider(), ('pack', None)))

        self.locator = locator
        self.device = device

        self.walker = SimpleFocusListWalker([])
        listbox = ListBox(self.walker)
        self.body.contents.append((listbox, ('weight', 1)))
        self.body.focus_position = 2
        self.add_hotkey('u', self.update, "update")
        self.update()

    def update(self):
        self.walker.clear()
        locator = self.locator
        def cmd_cb(lines):
            for line in self.error_filter(lines): pass

        button = Button("Connect")
        def button_cb(button, locator):
            self.tui.controller.connect(cmd_cb, locator)
        urwid.connect_signal(button, 'click', button_cb, locator)
        self.walker.append(AttrMap(button, None, focus_map='selected'))
        self.add_hotkey('c', partial(button_cb, button, locator), "connect")

        button = Button("Disconnect")
        def button_cb(button, locator):
            self.tui.controller.disconnect(cmd_cb, locator)
        urwid.connect_signal(button, 'click', button_cb, locator)
        self.walker.append(AttrMap(button, None, focus_map='selected'))
        self.add_hotkey('d', partial(button_cb, button, locator), "disconnect")

        button = Button("Start")
        def button_cb(button, locator):
            self.tui.controller.start(cmd_cb, locator)
        urwid.connect_signal(button, 'click', button_cb, locator)
        self.walker.append(AttrMap(button, None, focus_map='selected'))
        self.add_hotkey('s', partial(button_cb, button, locator), "start")

        button = Button("Abort")
        def button_cb(button, locator):
            self.tui.controller.stop(cmd_cb, locator)
        urwid.connect_signal(button, 'click', button_cb, locator)
        self.walker.append(AttrMap(button, None, focus_map='selected'))
        self.add_hotkey('a', partial(button_cb, button, locator), "abort")

        button = Button("Load File")
        def button_cb(button, locator):
            window = FileListWindow(self.tui, locator, self.device)
            self.tui.push_window(window)
        urwid.connect_signal(button, 'click', button_cb, locator)
        self.walker.append(AttrMap(button, None, focus_map='selected'))
        self.add_hotkey('l', partial(button_cb, button, locator), "load")

class WebcamWindow(Window):
    def __init__(self, tui):
        super().__init__(tui)
        self.body.contents.append((Text("Available Webcams"), ('pack', None)))
        self.body.contents.append((Divider(), ('pack', None)))

        self.walker = SimpleFocusListWalker([])
        listbox = ListBox(self.walker)
        self.body.contents.append((listbox, ('weight', 1)))
        self.body.focus_position = 2
        self.add_hotkey('u', self.update, "update")
        self.update()

    def update(self):
        def camlist_cb(webcams):
            self.walker.clear()
            def button_cb(locator, url, button):
                webbrowser.open_new(url)
                self.tui.pop_window()
            for locator, name, url in webcams:
                button = Button(name)
                urwid.connect_signal(button, 'click', button_cb, user_args=[locator, url])
                self.walker.append(AttrMap(button, None, focus_map='selected'))
        self.tui.controller.get_camlist(camlist_cb)

class DeviceListWindow(Window):
    def __init__(self, tui):
        super().__init__(tui)
        self.body.contents.append((Text("Available CNC Devices"), ('pack', None)))
        self.body.contents.append((Divider(), ('pack', None)))

        self.walker = SimpleFocusListWalker([])
        listbox = ListBox(self.walker)
        self.body.contents.append((listbox, ('weight', 1)))
        self.body.focus_position = 2
        self.add_hotkey('u', self.update, "update")
        self.add_hotkey('w', self.webcams, "webcams")
        self.update()

    def webcams(self):
        window = WebcamWindow(self.tui)
        self.tui.push_window(window)

    def update(self):
        def devlist_cb(devices):
            self.walker.clear()
            def button_cb(locator, device, button):
                window = DeviceWindow(self.tui, locator, device)
                self.tui.push_window(window)
            for locator, device in devices:
                button = Button(device)
                urwid.connect_signal(button, 'click', button_cb, user_args=[locator, device])
                self.walker.append(AttrMap(button, None, focus_map='selected'))
        self.tui.controller.get_devlist(devlist_cb)

class Tui():
    def __init__(self, asyncio_loop, controller):
        urwid.command_map['j'] = 'cursor down'
        urwid.command_map['k'] = 'cursor up'
        self.controller = controller
        self.windowstack = []

        self.asyncio_loop = asyncio_loop
        evl = urwid.AsyncioEventLoop(loop=asyncio_loop)
        window = DeviceListWindow(self)
        self.mainloop = urwid.MainLoop(window, palette,
                unhandled_input=self._unhandled_input, event_loop=evl)

    def toggle_log(self):
        if type(self.mainloop.widget) != Columns:
            columns = Columns([self.mainloop.widget, LogWindow(self)], 1)
            self.mainloop.widget = columns
        else:
            window = self.mainloop.widget[0]
            self.mainloop.widget = window

    def push_window(self, window):
        rootwidget = self.mainloop.widget
        if type(rootwidget) != Columns:
            self.windowstack.append(rootwidget)
            self.mainloop.widget = window
        else:
            self.windowstack.append(rootwidget[0])
            rootwidget.contents[0] = (window, rootwidget.options(box_widget=True))

    def pop_window(self):
        if not self.windowstack: return
        window = self.windowstack.pop()
        window.update()
        rootwidget = self.mainloop.widget
        if type(rootwidget) != Columns:
            self.mainloop.widget = window
        else:
            rootwidget.contents[0] = (window, rootwidget.options(box_widget=True))

    def _unhandled_input(self, key):
        if key == 'q':
            self.pop_window()
        elif key == 'Q':
            self.asyncio_loop.stop()
        elif key == 'L':
            self.toggle_log()
        else:
            return False
        return True

    def __enter__(self):
        self.mainloop.start()

    def __exit__(self, exceptiontype, exceptionvalue, traceback):
        """Restore terminal and allow exceptions"""
        self.mainloop.stop()
        return False
