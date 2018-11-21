#!/usr/bin/python3 -tt

import asyncio, concurrent
import curses
from functools import partial
from pubmarine import PubPen
import logging as log

PATH = '../.cncd.sock'

class Display:
    def __init__(self, pubpen, stdscr):
        self.pubpen = pubpen
        self.stdscr = stdscr
        self.pubpen.subscribe('incoming', self.show_message)
        self.pubpen.subscribe('typed', self.show_typing)

    async def get_ch(self):
        while True:
            future = self.pubpen.loop.run_in_executor(None, self.stdscr.getch)
            char = chr(await future)
            self.pubpen.publish('typed', char)
    def show_message(self, message, user):
        print(message, user)
    def show_typing(self, char):
        self.stdscr.addstr(0, 0, char.encode('utf-8'))
        self.pubpen.publish('outgoing', char)

class TalkProtocol(asyncio.Protocol):
    def __init__(self, pubpen):
        self.pubpen = pubpen
        self.pubpen.subscribe('outgoing', self.send_message)
    def send_message(self, message):
        self.transport.write(message.encode('utf-8'))
    def connection_made(self, transport):
        self.transport = transport
    def data_received(self, data):
        self.pubpen.publish('incoming', data.decode('utf-8', errors='replace'), "<you>")
    def error_received(self, exc):
        self.pubpen.publish('error', exc)
    def connection_lost(self, exc):
        self.pubpen.publish('conn_lost', exc)
        self.pubpen.loop.stop()

def mainloop(loop, pubpen, stdscr):
    display = Display(pubpen, stdscr)
    task = loop.create_task(display.get_ch())
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        #task.cancel()
        print("oh noes")

    pending = asyncio.Task.all_tasks()
    for task in pending: task.cancel()
    #try:
    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    #except Exception as e:
        #print("err")
    ##finally:
    #loop.close()

def main():
    loop = asyncio.get_event_loop()
    pubpen = PubPen(loop)

    future = loop.create_unix_connection(partial(TalkProtocol, pubpen), PATH)
    try:
        transport, protocol = loop.run_until_complete(future)
    except ConnectionRefusedError as e:
        log.fatal("Unable to set up connection")
        loop.close()
        return
    curses.wrapper(partial(mainloop, loop, pubpen))
    transport.close()
    loop.stop()

if __name__ == '__main__':
    main()
