#!/usr/bin/python3

import asyncio, concurrent
import curses
from functools import partial
import logging as log

PATH = '../.cncd.sock'

class Display:
    def __init__(self, logic, stdscr):
        self.stdscr = stdscr
        self.logic = logic
        logic.display = self

    async def get_ch(self, queue):
        curses.halfdelay(1)
        while True:
            loop = asyncio.get_event_loop()
            future = loop.run_in_executor(None, self.stdscr.getch)
            char = await future
            if char == -1: continue
            await queue.put(char)

    async def rcv_ch(self, queue):
        while True:
            char = await queue.get()
            self.status(f"recv char, {char}")
            if char == curses.KEY_RESIZE:
                self.resize()
            else:
                self.logic.keystroke(chr(char))

    def show_message(self, message, user):
        self.status(message)

    def status(self, msg):
        y, x = self.stdscr.getmaxyx()
        try:
            self.stdscr.addstr(y-1, 0, msg[:x-1])
        except:
            pass
        self.stdscr.refresh()

    def resize(self):
        y, x = self.stdscr.getmaxyx()
        self.stdscr.clear()
        self.stdscr.refresh()
        self.status(f"Resized to {y},{x}")

class Logic():
    def __init__(self):
        self.protocol = None
        self.display = None
    async def init(self):
        self.protocol.send_message("devlist", self.recv_devlist)

    def recv_devlist(self, lines):
        for line in lines:
            self.display.status(line)

    def receive(self, data):
        self.display.status(data)
    def keystroke(self, char):
        if char == 'q':
            loop = asyncio.get_event_loop()
            loop.stop()

        #self.protocol.send_message(chr(char))
        pass

class TalkProtocol(asyncio.Protocol):
    def __init__(self, logic):
        self.logic = logic
        logic.protocol = self
        self.waiters = {}
        self.nonce = 1
        self.data = ""
    def send_message(self, message, response_handler = None):
        self.transport.write(f"{self.nonce} {message}\n".encode())
        self.waiters[self.nonce] = (response_handler, [])
        self.nonce += 1
    def connection_made(self, transport):
        self.transport = transport
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
        pass

def done(cleanfunc, future):
    try:
        r = future.result()
    except concurrent.futures._base.CancelledError:
        pass
    except Exception as e:
        loop = asyncio.get_event_loop()
        loop.stop()
        cleanfunc()
        print("err", e)

def setup_term():
    stdscr = curses.initscr()
    curses.noecho()
    curses.cbreak()
    return stdscr
def cleanup_term(stdscr):
    curses.nocbreak()
    stdscr.keypad(False)
    curses.echo()
    curses.endwin()

def main(loop):
    logic = Logic()

    future = loop.create_unix_connection(partial(TalkProtocol, logic), PATH)
    try:
        transport, protocol = loop.run_until_complete(future)
    except ConnectionRefusedError as e:
        log.fatal("Unable to set up connection")
        return

    stdscr = setup_term()
    display = Display(logic, stdscr)
    queue = asyncio.Queue()
    task = asyncio.ensure_future(display.get_ch(queue))
    task.add_done_callback(partial(done, partial(cleanup_term, stdscr)))
    task = asyncio.ensure_future(display.rcv_ch(queue))
    task.add_done_callback(partial(done, partial(cleanup_term, stdscr)))
    task = asyncio.ensure_future(logic.init())
    task.add_done_callback(partial(done, partial(cleanup_term, stdscr)))

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass

    ## first clean up curses
    cleanup_term(stdscr)
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

#TODO make status bar, remove logging
#sock from cmdline
