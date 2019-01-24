import asyncio, sys
from flask import current_app, g

sys.path.append('..')
## maybe connect should return a controller
from libcnc.cnc import Controller, connect

def cncd_connect():
    if 'connected' in g:
        return g.controller

    loop = asyncio.get_event_loop("cncd")
    r = connect(loop, current_app.config['socket_path'])
    transport, protocol = r
    controller = Controller(protocol)
    g.transport = transport
    g.protocol = protocol
    g.controller = controller
    return g.controller

def cncd_disconnect(error = None):
    if 'connected' in g:
        g.transport.close()
        ## todo, destroy loop?

def init_app(app):
    app.teardown_appcontext(cncd_disconnect)
