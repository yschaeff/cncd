#!/usr/bin/python3

import urwid
from urwid import Frame, Text, Filler, AttrMap, ListBox, Divider, SimpleFocusListWalker,\
    Button, WidgetWrap, Pile, ExitMainLoop, Columns, Edit, Padding, BoxAdapter,\
    SimpleListWalker, ProgressBar
from functools import partial
import logging as log
import re, time
import webbrowser
import shlex
import json
from collections import defaultdict

EDIT_KEYS = ["backspace", "delete", "home", "end", "left", "right", "enter"]
NUMERICALS = [i for i in "0123456789.+-"] + EDIT_KEYS

palette = [('status', 'white,bold', 'dark blue'), \
        ('selected', 'black', 'white'),

        ('default', 'dark cyan', 'black'),
        ('info', 'white', 'black'),
        ('warning', 'yellow', 'black'),
        ('error', 'light red', 'black'),
        ('critical', 'white', 'dark red'),

        ('progress_normal', 'black', 'light gray'),
        ('progress_complete', 'white', 'brown'),

        ('Tlabel', 'yellow', 'black'),
        ('Flabel', 'white', 'black')]

class NamedProgressBar(ProgressBar):
    def __init__(self, label, normal, complete, current=0, done=100, satt=None):
        if int(done) == 0: done = 100
        self.label = label
        super().__init__(normal, complete, current, done, satt)
    def get_text(self):
        return self.label

class Window(urwid.WidgetWrap):
    def __init__(self, tui):
        self.tui = tui
        self.header_str = "Q:quit q:previous L:log"
        self.header = Text(self.header_str)
        self.body = Pile([])
        self.footer = Text("No messages")
        self.footerpile = Pile([self.footer])
        self.frame = Frame(self.body,
            AttrMap(self.header, 'status'), AttrMap(self.footerpile, 'status'), 'body')
        urwid.WidgetWrap.__init__(self, self.frame)
        self.hotkeys = {} ## key:func
        self.add_hotkey(':', self.start_prompt, 'cmd')
        self.add_hotkey('u', self.sync, 'sync')

    def actions(self):
        window = ActionWindow(self.tui)
        self.tui.push_window(window)

    def sync(self):
        lines = self.tui.controller.sync()
        self.footer.set_text(lines[-1].strip())

    def webcams(self):
        window = WebcamWindow(self.tui)
        self.tui.push_window(window)

    def start_prompt(self):
        def end_prompt(edit_text):
            self.footerpile.contents.pop()
            self.frame.focus_part='body'
            def cb(json_msg):
                if json_msg:
                    self.footer.set_text(json.dumps(json_msg))
                else:
                    self.footer.set_text("ok")
            self.tui.controller.action(edit_text, cb)
        prompt = CB_Hist_Edit(":", "", None, end_prompt, self.tui.command_history)
        self.footerpile.contents.append((AttrMap(prompt, 'info'), ('pack', None)))
        self.frame.focus_part='footer'
        self.footerpile.focus_position = 1

    def update(self):
        """Fetch new information and update labels, overwrite me"""
        pass

    def display_errors(self, json_msg):
        error = json_msg.get('ERROR', None)
        if error:
            self.footer.set_text("ERROR: {}".format(error.strip()))
        else:
            self.footer.set_text("")

    def add_hotkey(self, key, func, label, omit_header=False):
        if key not in self.hotkeys:
            self.hotkeys[key] = func
            if not omit_header:
                self.header_str += " {}:{}".format(key, label)
                self.header.set_text(self.header_str)

    def keypress(self, size, key):
        if super().keypress(size, key) == None:
            return None
        if key in self.hotkeys:
            self.hotkeys[key]()
            return None
        return key

    ## subscribe / unsubscribe here
    def start(self): pass
    def stop(self): pass

class ScrollingListBox(ListBox):
    def render(self, size, focus=False):
        cols, rows = size
        while len(self.body) > 2*rows+1:
            self.body.pop(0)
        l = len(self.body)
        if l > 0:
            self.body.set_focus(l-1)
        return super().render(size, focus)

class LogWindow(Window):
    def __init__(self, tui):
        super().__init__(tui)
        description = Text("NOTICE. The log displayed here is a copy of the "
            "daemon log. Keeping the the loglevel at debug impacts "
            "performance. When done, run ':loglevel warning'")
        self.body.contents.append((description, ('pack', None)))
        self.walker = SimpleFocusListWalker([])
        self.listbox = ScrollingListBox(self.walker)
        self.body.contents.append((self.listbox, ('weight', 1)))
        #self.add_hotkey('-', self.update, "increase")
        #self.add_hotkey('+', self.update, "decrease")
        #c e w i d

    def wrap(self, line):
        if line.startswith('CRITICAL'):
            focusmap = 'critical'
        elif line.startswith('ERROR'):
            focusmap = 'error'
        elif line.startswith('WARNING'):
            focusmap = 'warning'
        elif line.startswith('INFO'):
            focusmap = 'info'
        else:
            focusmap = 'default'

        txt = Text(line.strip())
        return AttrMap(txt, focusmap)

    def start(self):
        self.walker.append(Text("---- START LOGGING ----", align='center'))
        def log_cb(json_msg):
            line = json_msg.get('log', None)
            if not line:
                return
            self.walker.append(self.wrap(line))
        self.tui.controller.start_logs(log_cb)

    def stop(self):
        self.tui.controller.stop_logs()

class CB_Edit(Edit):
    def __init__(self, caption, edit_text, type_cb, enter_cb, whitelist=None):
        super().__init__(caption, edit_text)
        self.type_cb = type_cb
        self.enter_cb = enter_cb
        self.whitelist = whitelist
    def keypress(self, size, key):
        if key == 'enter' and self.enter_cb:
            self.enter_cb(self.get_edit_text())
            return None
        if self.whitelist and key not in self.whitelist:
            return key
        handled = super().keypress(size, key)
        if self.type_cb: self.type_cb(self.get_edit_text())
        return handled

class CB_Hist_Edit(CB_Edit):
    def __init__(self, caption, edit_text, type_cb, enter_cb, history):
        super().__init__(caption, edit_text, type_cb, enter_cb)
        self.history = history
        self.index = len(history)
        self.mem = None
    def keypress(self, size, key):
        if key == 'enter':
            self.history.append(self.get_edit_text())
        elif key == 'esc': ## cancel input
            self.set_edit_text("")
            key = 'enter'
        handled = super().keypress(size, key)
        if not handled: return handled

        if self.index == len(self.history) and (key=='up' or key=='down'):
            self.mem = self.get_edit_text()

        if key == 'up':
            self.index = max(0, self.index-1)
            self.set_edit_text(self.history[self.index])
            self.move_cursor_to_coords(size, 100, 0)
            return None
        elif key == 'down':
            self.index = min(len(self.history), self.index+1)
            if self.index >= len(self.history):
                self.set_edit_text(self.mem)
            else:
                self.set_edit_text(self.history[self.index])
            self.move_cursor_to_coords(size, 100, 0)
            return None
        return key


class FileListWindow(Window):
    def __init__(self, tui, locator, device):
        super().__init__(tui)
        self.body.contents.append((Text("Select file to load on \"{}\"".format(device)), ('pack', None)))
        self.body.contents.append((Divider(), ('pack', None)))
        self.device = device

        self.locator = locator
        self.device = device
        self.all_files = []

        def limit(regexp):
            self.regexp = regexp
            self.populate_list()
        def enter(edit_text):
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
        try:
            p = re.compile(self.regexp, re.IGNORECASE)
        except re.error:
            filtered_files = self.all_files
        else:
            filtered_files = filter(p.search, self.all_files)

        def button_cb(locator, filename, button):
            self.filename = filename
            self.tui.controller.set_filename(locator, filename)
            self.tui.pop_window()
        self.walker.clear()
        for line in filtered_files:
            filename = line.strip()
            button = Button(filename)
            urwid.connect_signal(button, 'click', button_cb, user_args=[self.locator, filename])
            self.walker.append(AttrMap(button, None, focus_map='selected'))

    def update(self):
        def filelist_cb(json_msg):
            self.display_errors(json_msg)
            self.all_files = json_msg.get('files', [])
            self.populate_list()
        self.tui.controller.get_filelist(filelist_cb, self.locator)

class ManualControlWindow(Window):
    def __init__(self, tui, locator, device):
        super().__init__(tui)
        self.locator = locator
        self.device = device

        self.add_hotkey('U', self.update, "update")
        self.add_hotkey('w', self.webcams, "webcams")
        self.add_hotkey('a', self.actions, "actions")

        self.body.contents.append((Text("Selected device \"{}\"".format(device)), ('pack', None)))
        self.body.contents.append((Divider(), ('pack', None)))

        self.walker = SimpleFocusListWalker([])
        listbox = ListBox(self.walker)
        self.body.contents.append((listbox, ('weight', 1)))
        self.body.focus_position = 2
        self.update()

    def update(self):
        self.walker.clear()
        locator = self.locator
        def cmd_cb(json_msg):
            self.display_errors(json_msg)

        button = Button("[h] Home (G28 W)")
        def button_cb(button, locator):
            self.tui.controller.action("gcode {} 'G28 W'".format(locator), cmd_cb)
        urwid.connect_signal(button, 'click', button_cb, locator)
        self.walker.append(AttrMap(button, None, focus_map='selected'))
        self.add_hotkey('h', partial(button_cb, button, locator), "home", omit_header=True)

        def edit_cb(txt):
            self.tui.controller.action("gcode {} 'G90'".format(locator), cmd_cb)
            self.tui.controller.action("gcode {} 'G1 X{}'".format(locator, txt), cmd_cb)
        edit = CB_Edit("Move to ABS X (mm): ", "0", None, edit_cb, NUMERICALS)
        self.walker.append(AttrMap(edit, None, focus_map='selected'))

        def edit_cb(txt):
            self.tui.controller.action("gcode {} 'G90'".format(locator), cmd_cb)
            self.tui.controller.action("gcode {} 'G1 Y{}'".format(locator, txt), cmd_cb)
        edit = CB_Edit("Move to ABS Y (mm): ", "0", None, edit_cb, NUMERICALS)
        self.walker.append(AttrMap(edit, None, focus_map='selected'))

        def edit_cb(txt):
            self.tui.controller.action("gcode {} 'G90'".format(locator), cmd_cb)
            self.tui.controller.action("gcode {} 'G1 Z{}'".format(locator, txt), cmd_cb)
        edit = CB_Edit("Move to ABS Z (mm): ", "0", None, edit_cb, NUMERICALS)
        self.walker.append(AttrMap(edit, None, focus_map='selected'))

        def edit_cb(txt):
            self.tui.controller.action("gcode {} 'G1 F{}'".format(locator, txt), cmd_cb)
        edit = CB_Edit("Set Feedrate mm/min: ", "", None, edit_cb, NUMERICALS)
        self.walker.append(AttrMap(edit, None, focus_map='selected'))

        def edit_cb(txt):
            self.tui.controller.action("gcode {} 'M104 S{}'".format(locator, txt), cmd_cb)
        edit = CB_Edit("Set Extruder Temperature °C: ", "0", None, edit_cb, NUMERICALS)
        self.walker.append(AttrMap(edit, None, focus_map='selected'))

        def edit_cb(txt):
            self.tui.controller.action("gcode {} 'M140 S{}'".format(locator, txt), cmd_cb)
        edit = CB_Edit("Set Bed Temperature °C: ", "0", None, edit_cb, NUMERICALS)
        self.walker.append(AttrMap(edit, None, focus_map='selected'))

        button = Button("[L] Load filament (G1 E100 F300)")
        def button_cb(button, locator):
            self.tui.controller.action("gcode {} 'G91'".format(locator), cmd_cb)
            self.tui.controller.action("gcode {} 'G1 E100 F300'".format(locator), cmd_cb)
        urwid.connect_signal(button, 'click', button_cb, locator)
        self.walker.append(AttrMap(button, None, focus_map='selected'))
        self.add_hotkey('L', partial(button_cb, button, locator), "load", omit_header=True)

        button = Button("[U] Unload filament (G1 E-100 F2000)")
        def button_cb(button, locator):
            self.tui.controller.action("gcode {} 'G91'".format(locator), cmd_cb)
            self.tui.controller.action("gcode {} 'G1 E-100 F2000'".format(locator), cmd_cb)
        urwid.connect_signal(button, 'click', button_cb, locator)
        self.walker.append(AttrMap(button, None, focus_map='selected'))
        self.add_hotkey('U', partial(button_cb, button, locator), "unload", omit_header=True)

        button = Button("[r] Release steppers (M18)")
        def button_cb(button, locator):
            self.tui.controller.action("gcode {} 'M18'".format(locator), cmd_cb)
        urwid.connect_signal(button, 'click', button_cb, locator)
        self.walker.append(AttrMap(button, None, focus_map='selected'))
        self.add_hotkey('r', partial(button_cb, button, locator), "release", omit_header=True)

        self.walker.append(Divider())

        def enter_cb(edit, txt):
            if edit.hjkl_active:
                edit.hjkl_active = False
                edit.set_edit_text( "[enter] to activate / deactivate" )
            else:
                edit.hjkl_active = True
                edit.set_edit_text( "" )
                self.footer.set_text("Use keys 'hjklaz' to move printer.")
        def edit_cb(edit, txt):
            if not edit.hjkl_active: return
            key = txt[-1]
            m = {'h':"X-",'l':"X",'j':"Y-",'k':"Y",'a':"Z",'z':"Z-"}
            if key not in m:
                self.footer.set_text("key '{}' not handled. Please use keys 'hjklaz' to move printer.".format(key))
                return
            edit.set_edit_text("{}".format(m[key]))
            increment = 10
            c = "gcode {} 'G1 ".format(locator) + m[key] + "{}'".format(increment)
            self.tui.controller.action("gcode {} 'G91'".format(locator), cmd_cb)
            self.tui.controller.action(c, cmd_cb)

            #self.tui.controller.action("gcode {} 'G1 F{}'".format(locator, txt), cmd_cb)
        edit = CB_Edit("VI Move: ", "[enter] to activate", edit_cb, enter_cb, [i for i in "hjklaz"])
        edit.type_cb = partial(edit_cb, edit) ##hack to solve cyclic dependency
        edit.enter_cb = partial(enter_cb, edit) ##hack to solve cyclic dependency
        edit.hjkl_active = False
        self.walker.append(AttrMap(edit, None, focus_map='selected'))

        ## maybe set relative extruder first M83
        ##M18 release steppers



class DeviceWindow(Window):
    def __init__(self, tui, locator, device):
        super().__init__(tui)
        self.body.contents.append((Text("Selected device \"{}\"".format(device)), ('pack', None)))
        fn = self.tui.controller.get_filename(locator)
        self.filename_txt = Text("Selected file \"{}\"".format(fn))
        self.body.contents.append((self.filename_txt, ('pack', None)))
        self.body.contents.append((Divider(), ('pack', None)))

        self.statuswidget = Pile([])
        self.body.contents.append((self.statuswidget, ('pack', None)))
        self.body.contents.append((Divider(), ('pack', None)))

        self.locator = locator
        self.device = device

        self.walker = SimpleFocusListWalker([])
        listbox = ListBox(self.walker)
        self.body.contents.append((listbox, ('weight', 1)))
        self.body.focus_position = 5
        self.add_hotkey('U', self.update, "update")
        self.add_hotkey('w', self.webcams, "webcams")
        self.add_hotkey('a', self.actions, "actions")
        self.status = defaultdict(str)
        self.update()

    def start(self):
        self.update()
        self.tui.controller.subscribe(partial(self.update_status_cb, self.statuswidget), self.locator)

    def stop(self):
        self.tui.controller.unsubscribe(None, self.locator)

    def update_status_cb(self, container, json_msg):
        self.display_errors(json_msg)
        ## TODO filter error from loop below. The results should be in a known
        ## section like 'i3'
        data = json_msg.get(self.locator, {})
        for key, value in data.items():
            self.status[key] = value

        def parse_time(status, container, ignore):
            try:
                tstart = float(status['starttime'])
                tstop = float(status['stoptime'])
                offset = self.tui.controller.time_offset
                if tstop == -1:
                    d = time.time() - tstart - offset
                else:
                    d = tstop - tstart
                t = time.asctime( time.localtime(tstart+offset) )
                txt = "Started at {} ({}h{}m)".format(t, int(d/3600), int(d%3600)//60)
                attr = 'Flabel'
                w = AttrMap(Text(txt), attr, attr)
                container.contents.append((w, container.options('pack')))
            except ValueError:
                pass
            finally:
                ignore.append('starttime')
                #ignore.append('stoptime') ## leave for debugging for now

        def parse_progress(status, container, ignore):
            try:
                fsize = int(status['filesize'])
                fprog = int(status['progress'])
                tstart = float(status['starttime'])
                tstop = float(status['stoptime'])
                cz = float(status['current_z'])
                fz = float(status['final_z'])
                ce = float(status['current_e'])
                fe = float(status['final_e'])
                offset = self.tui.controller.time_offset
                if tstop == -1:
                    d = time.time() - tstart - offset
                else:
                    d = tstop - tstart
                rate = fprog/fsize
                attr = 'Flabel'
                def div(a, b):
                    if b == 0:
                        return 0
                    return a/b

                label = "File: {:0.0f}/{:0.0f} Kb ({:0.2f}%)".format(fprog/1024, fsize/1024, rate*100)
                bar = NamedProgressBar(label, 'progress_normal', 'progress_complete', fprog, fsize, 'status')
                container.contents.append((bar, container.options('pack')))

                label = "Z Travel: {:0.2f}/{:0.2f} mm ({:0.2f}%)".format(cz, fz, div(cz,fz)*100)
                bar = NamedProgressBar(label, 'progress_normal', 'progress_complete', cz, fz, 'status')
                container.contents.append((bar, container.options('pack')))

                label = "Extruded: {:0.0f}/{:0.0f} mm ({:0.2f}%)".format(ce, fe, div(ce,fe)*100)
                bar = NamedProgressBar(label, 'progress_normal', 'progress_complete', ce, fe, 'status')
                container.contents.append((bar, container.options('pack')))
            except:
                pass
            finally:
                ignore.append('filesize')
                ignore.append('progress')
                ignore.append('current_z')
                ignore.append('final_z')
                ignore.append('current_e')
                ignore.append('final_e')

        def parse_status(status, container, ignore):
            stat_cols = Columns([], 0)
            w = make_w(stat_cols, 'connected', 'connected', 'disconnected')
            w = make_w(stat_cols, 'idle', 'active', 'idle', reverse=True)
            w = make_w(stat_cols, 'paused', 'paused', 'operating')
            container.contents.append((stat_cols, container.options('pack')))
            ignore.append('connected')
            ignore.append('idle')
            ignore.append('paused')

        def make_w(container, key, Tlabel, Flabel, reverse=False):
            if (self.status[key] == True) ^ reverse:
                label = "[{}]".format(Tlabel)
                attr = 'Tlabel'
            else:
                label = "[{}]".format(Flabel)
                attr = 'Flabel'
            w = AttrMap(Text(label), attr, attr)
            container.contents.append((w, container.options('pack')))
        ignore = ['last_temp_request']
        # We really got to properly parse this to some struct first
        container.contents.clear()
        ## progress
        parse_status(self.status, container, ignore)
        parse_progress(self.status, container, ignore)
        parse_time(self.status, container, ignore)

        for key, value in sorted(self.status.items()):
            if key in ignore: continue
            attr = 'Flabel'
            w = AttrMap(Text("{}: {}".format(key, value)), attr, attr)
            container.contents.append((w, container.options('pack')))

    def update_status(self):
        self.tui.controller.get_data(partial(self.update_status_cb, self.statuswidget), self.locator)

    def update(self):
        self.update_status()
        self.walker.clear()
        locator = self.locator
        def cmd_cb(json_msg):
            self.display_errors(json_msg)
            self.update_status()

        fn = self.tui.controller.get_filename(locator)
        self.filename_txt.set_text("Selected file \"{}\"".format(fn))

        button = Button("[c] Connect")
        def button_cb(button, locator):
            self.tui.controller.connect(cmd_cb, locator)
        urwid.connect_signal(button, 'click', button_cb, locator)
        self.walker.append(AttrMap(button, None, focus_map='selected'))
        self.add_hotkey('c', partial(button_cb, button, locator), "connect", omit_header=True)

        button = Button("[D] Disconnect")
        def button_cb(button, locator):
            self.tui.controller.disconnect(cmd_cb, locator)
        urwid.connect_signal(button, 'click', button_cb, locator)
        self.walker.append(AttrMap(button, None, focus_map='selected'))
        self.add_hotkey('D', partial(button_cb, button, locator), "disconnect", omit_header=True)

        button = Button("[s] Start")
        def button_cb(button, locator):
            fn = self.tui.controller.get_filename(locator)
            if not fn:
                self.footer.set_text("Please Select a file first")
                return
            self.tui.controller.start(cmd_cb, locator, self.tui.controller.get_filename(locator))
        urwid.connect_signal(button, 'click', button_cb, locator)
        self.walker.append(AttrMap(button, None, focus_map='selected'))
        self.add_hotkey('s', partial(button_cb, button, locator), "start", omit_header=True)

        button = Button("[S] Stop (ask nicely to stop)")
        def button_cb(button, locator):
            self.tui.controller.stop(cmd_cb, locator)
        urwid.connect_signal(button, 'click', button_cb, locator)
        self.walker.append(AttrMap(button, None, focus_map='selected'))
        self.add_hotkey('S', partial(button_cb, button, locator), "stop", omit_header=True)

        button = Button("[!] Abort (Interrupt then disconnect)")
        def button_cb(button, locator):
            self.tui.controller.abort(cmd_cb, locator)
        urwid.connect_signal(button, 'click', button_cb, locator)
        self.walker.append(AttrMap(button, None, focus_map='selected'))
        self.add_hotkey('!', partial(button_cb, button, locator), "abort", omit_header=True)

        button = Button("[p] Pause")
        def button_cb(button, locator):
            self.tui.controller.pause(cmd_cb, locator)
        urwid.connect_signal(button, 'click', button_cb, locator)
        self.walker.append(AttrMap(button, None, focus_map='selected'))
        self.add_hotkey('p', partial(button_cb, button, locator), "pause", omit_header=True)

        button = Button("[r] Resume")
        def button_cb(button, locator):
            self.tui.controller.resume(cmd_cb, locator)
        urwid.connect_signal(button, 'click', button_cb, locator)
        self.walker.append(AttrMap(button, None, focus_map='selected'))
        self.add_hotkey('r', partial(button_cb, button, locator), "resume", omit_header=True)

        button = Button("[l] Load File")
        def button_cb(button, locator):
            window = FileListWindow(self.tui, locator, self.device)
            self.tui.push_window(window)
        urwid.connect_signal(button, 'click', button_cb, locator)
        self.walker.append(AttrMap(button, None, focus_map='selected'))
        self.add_hotkey('l', partial(button_cb, button, locator), "load", omit_header=True)

        button = Button("[m] Manual Control")
        def button_cb(button, locator):
            window = ManualControlWindow(self.tui, locator, self.device)
            self.tui.push_window(window)
        urwid.connect_signal(button, 'click', button_cb, locator)
        self.walker.append(AttrMap(button, None, focus_map='selected'))
        self.add_hotkey('m', partial(button_cb, button, locator), "manual", omit_header=True)

class ActionWindow(Window):
    def __init__(self, tui):
        super().__init__(tui)
        self.body.contents.append((Text("Available Actions"), ('pack', None)))
        self.body.contents.append((Divider(), ('pack', None)))

        self.walker = SimpleFocusListWalker([])
        listbox = ListBox(self.walker)
        self.body.contents.append((listbox, ('weight', 1)))
        self.body.focus_position = 2
        self.add_hotkey('U', self.update, "update")
        self.update()

    def update(self):
        def action_cb(json_msg):
            self.walker.clear()
            def button_cb(cmd, button):
                self.tui.controller.action(cmd, None)
                self.tui.pop_window()
            self.display_errors(json_msg)
            actions = json_msg.get('actions', None)
            if not actions: return
            for action in actions:
                cmd = action['command']
                label = action['short']
                description = action['long']
                button = Button("[{}] - {}".format(label, description))
                urwid.connect_signal(button, 'click', button_cb, user_args=[cmd])
                self.walker.append(AttrMap(button, None, focus_map='selected'))
        self.tui.controller.get_actions(action_cb)

class WebcamWindow(Window):
    def __init__(self, tui):
        super().__init__(tui)
        self.body.contents.append((Text("Available Webcams"), ('pack', None)))
        self.body.contents.append((Divider(), ('pack', None)))

        self.walker = SimpleFocusListWalker([])
        listbox = ListBox(self.walker)
        self.body.contents.append((listbox, ('weight', 1)))
        self.body.focus_position = 2
        self.add_hotkey('U', self.update, "update")
        self.update()

    def update(self):
        def camlist_cb(json_msg):
            self.walker.clear()
            def button_cb(locator, url, button):
                webbrowser.open_new(url)
                self.tui.pop_window()
            self.display_errors(json_msg)
            webcams = json_msg.get('webcams', None)
            if not webcams: return
            for locator, webcam in webcams.items():
                name = webcam["name"]
                url = webcam["url"]
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
        self.add_hotkey('U', self.update, "update")
        self.add_hotkey('w', self.webcams, "webcams")
        self.add_hotkey('a', self.actions, "actions")
        self.update()

    def update(self):
        def devlist_cb(json_msg):
            self.walker.clear()
            def button_cb(locator, device, button):
                window = DeviceWindow(self.tui, locator, device)
                self.tui.push_window(window)
            self.display_errors(json_msg)
            devices = json_msg.get('devices')
            if not devices: return
            for locator, device in devices.items():
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
        ## Urwid and asyncio do not entirely play nice.
        ## increase idle delay to prevent Urwid redawing 256 times a second.
        evl._idle_emulation_delay = 1/20
        window = DeviceListWindow(self)
        self.mainloop = urwid.MainLoop(window, palette,
                unhandled_input=self._unhandled_input, event_loop=evl)

        self.logwindow = LogWindow(self)
        self.command_history = ["loglevel debug", "loglevel warning", "help help"]

    def toggle_log(self):
        if type(self.mainloop.widget) != Columns:
            columns = Columns([self.mainloop.widget, self.logwindow], 1)
            self.mainloop.widget = columns
            self.logwindow.start()
        else:
            window = self.mainloop.widget[0]
            logwindow = self.mainloop.widget[1]
            self.logwindow.stop()
            self.mainloop.widget = window

    def push_window(self, window):
        window.start()
        rootwidget = self.mainloop.widget
        if type(rootwidget) != Columns:
            rootwidget.stop()
            self.windowstack.append(rootwidget)
            self.mainloop.widget = window
        else:
            self.windowstack.append(rootwidget[0])
            rootwidget[0].stop()
            rootwidget.contents[0] = (window, rootwidget.options(box_widget=True))

    def pop_window(self):
        if not self.windowstack: return
        window = self.windowstack.pop()
        #window.update()
        window.start()
        rootwidget = self.mainloop.widget
        if type(rootwidget) != Columns:
            self.mainloop.widget.stop()
            self.mainloop.widget = window
        else:
            oldwin = rootwidget.contents[0][0].stop()
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
        if exceptiontype:
            log.critical(exceptiontype)
            log.critical(exceptionvalue)
            log.critical(traceback)
        return False
