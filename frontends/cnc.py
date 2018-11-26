#!/usr/bin/python3

import asyncio, concurrent
import urwid
from functools import partial
import logging as log

PATH = '../.cncd.sock'

def item_chosen(button, choice):
    return
    global screen
    response = urwid.Text([u'You chose ', choice, u'\n'])
    done = urwid.Button(u'Ok')
    urwid.connect_signal(done, 'click', exit_program)
    screen.original_widget = urwid.Filler(urwid.Pile([response,
        urwid.AttrMap(done, None, focus_map='reversed')]))

def menu(title, choices):
    body = [urwid.Text(title), urwid.Divider()]
    for c in choices:
        button = urwid.Button(c)
        urwid.connect_signal(button, 'click', item_chosen, c)
        body.append(urwid.AttrMap(button, None, focus_map='reversed'))
    return urwid.ListBox(urwid.SimpleFocusListWalker(body))

class Logic():
    def __init__(self, screen):
        self.protocol = None
        self.screen = screen
    def init(self):
        def recv_devlist(lines):
            #make list
            raise Exception
            body = [urwid.Text("devices"), urwid.Divider()]
            for l in lines:
                button = urwid.Button(l)
                urwid.connect_signal(button, 'click', item_chosen, l)
                body.append(urwid.AttrMap(button, None, focus_map='reversed'))
            self.screen.original_widget = urwid.ListBox(urwid.SimpleFocusListWalker(body))
        self.protocol.send_message("devlist", recv_devlist)

    def receive(self, data):
        #self.display.status(data)
        pass
    def keystroke(self, char):
        if char == 'q':
            loop = asyncio.get_event_loop()
            loop.stop()
        pass

class CncProtocol(asyncio.Protocol):
    def __init__(self, logic, con_cb):
        self.logic = logic
        self.con_cb = con_cb
        logic.protocol = self
        self.waiters = {}
        self.nonce = 1
        self.data = ""
    def send_message(self, message, response_handler = None):
        self.transport.write(f"{self.nonce} {message}\n".encode())
        self.waiters[self.nonce] = (response_handler, [])
        self.nonce += 1
    def connection_made(self, transport):
        ##start interface
        self.transport = transport
        self.con_cb()
    def data_received(self, data):
        ## accumulate data
        self.data += data.decode()
        while True:
            ## new complete line ready?
            idx = self.data.find('\n')
            if idx == -1: break
            line = self.data[:idx+1]
            self.data = self.data[idx+1:]
            ## great, find nonce
            nonce_separator = line.find(' ')
            if nonce_separator == -1: continue
            s_nonce = line[:nonce_separator]
            line = line[nonce_separator+1:]
            try:
                nonce = int(s_nonce)
            except ValueError:
                continue
            if nonce not in self.waiters:
                assert(nonce in self.waiters) # remove me!
                continue
            handler, buf = self.waiters[nonce]
            if line.strip() == ".":
                handler(buf)
                self.waiters.pop(nonce)
            else:
                buf.append(line)
    def error_received(self, exc):
        pass
    def connection_lost(self, exc):
        loop = asyncio.get_event_loop()
        loop.stop()

def done(future):
    try:
        r = future.result()
    except concurrent.futures._base.CancelledError:
        pass
    except Exception as e:
        loop = asyncio.get_event_loop()
        loop.stop()
        print("err", e)

def exit_program(button):
    loop = asyncio.get_event_loop()
    loop.stop()

def main(loop):
    global screen
    tt = urwid.Filler(urwid.Text('Waiting for device list.'), 'top')
    screen = urwid.Overlay(tt, urwid.SolidFill(u'\N{MEDIUM SHADE}'),
        align='center', width=('relative', 80),
        valign='middle', height=('relative', 60),
        min_width=20, min_height=9)
    evl = urwid.AsyncioEventLoop(loop=asyncio.get_event_loop())
    urwid_loop = urwid.MainLoop(screen, event_loop=evl)
    urwid_loop.start()

    logic = Logic(screen)

    future = loop.create_unix_connection(partial(CncProtocol, logic, logic.init), PATH)
    try:
        transport, protocol = loop.run_until_complete(future)
    except ConnectionRefusedError as e:
        log.fatal("Unable to set up connection")
        return

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass

    ## first clean up curses
    urwid_loop.stop()
    log.debug("terminating")
    #then retrieve exceptions
    transport.close()
    pending = asyncio.Task.all_tasks()
    for task in pending: task.cancel()
    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

if __name__ == '__main__':
    log.basicConfig(level=log.DEBUG)
    loop = asyncio.get_event_loop()
    main(loop)
    loop.close()
