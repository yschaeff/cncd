#!/usr/bin/env python3

from aiohttp import web
import aiohttp_jinja2
import jinja2
from routes import setup_routes

import sys, asyncio
sys.path.append('..')
## maybe connect should return a controller
from libcnc.cnc import Controller, connect, CncProtocol

conf = {'unix_socket': '/tmp/cncd.sock'}

async def cncd_connect(app):
    conf = app['config']
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_unix_connection(CncProtocol, conf['unix_socket'])
    app['transport'] = transport
    app['protocol'] = protocol
    app['controller'] = Controller(protocol)

async def cncd_disconnect(error = None):
    app['transport'].close()

app = web.Application()
app['config'] = conf
app['static_root_url'] = '/static'
aiohttp_jinja2.setup(app, context_processors=[aiohttp_jinja2.request_processor],
        loader=jinja2.FileSystemLoader('./templates'))

app.on_startup.append(cncd_connect)
app.on_shutdown.append(cncd_disconnect)
setup_routes(app)

web.run_app(app)
