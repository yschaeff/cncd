#!/usr/bin/env python3

from aiohttp import web
import aiohttp_jinja2
import jinja2
from httpui.routes import setup_routes

from collections import defaultdict
from functools import partial
import sys, asyncio
## maybe connect should return a controller
from libcnc.cnc import Controller, connect, CncProtocol

conf = {'unix_socket': '/tmp/cncd.sock'}
conf = {'unix_socket': '/home/yuri/repo/cncd/.cncd.sock'}

async def cncd_connect(app):
    conf = app['config']
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_unix_connection(CncProtocol, conf['unix_socket'])
    app['transport'] = transport
    app['protocol'] = protocol
    app['controller'] = Controller(protocol)
    app['subscriber'] = Subscriber(app['controller'])

async def cncd_disconnect(error = None):
    app['transport'].close()

class Subscriber:
    def __init__(self, controller):
        self.controller = controller
        self.subscriptions = defaultdict(dict)
        self.ticket = 0
    def cb_wrapper(self, channel, msg):
        subscribers = self.subscriptions[channel]
        for ticket, callback in subscribers.items():
            callback(msg)
    def subscribe(self, channel, callback):
        subscribers = self.subscriptions[channel]
        if not subscribers:
            self.controller.subscribe(partial(self.cb_wrapper, channel), channel)
        ticket = self.ticket
        self.subscriptions[channel][ticket] = callback
        self.ticket += 1
        return ticket
    def unsubscribe(self, channel, ticket):
        if channel not in self.subscriptions: return
        subscribers = self.subscriptions[channel]
        try:
            subscribers.pop(ticket)
        except KeyError:
            pass
        if not subscribers:
            self.controller.unsubscribe(None, channel)

app = web.Application()
app['config'] = conf
app['static_root_url'] = '/static'
aiohttp_jinja2.setup(app, context_processors=[aiohttp_jinja2.request_processor],
        loader=jinja2.FileSystemLoader('httpui/templates'))

app.on_startup.append(cncd_connect)
app.on_shutdown.append(cncd_disconnect)
setup_routes(app)

try:
    web.run_app(app)
except ConnectionRefusedError:
    print("Connection refused.")


