from views import index, device_view, websocket_handler

def setup_static_routes(app):
    app.router.add_static('/static/', path='./static', name='static')

def setup_routes(app):
    setup_static_routes(app)
    app.router.add_get('/', index)
    app.router.add_get('/{device}/', device_view, name='device')
    app.router.add_post('/{device}/', device_view, name='device')
    app.router.add_get('/{device}/ws', websocket_handler, name='ws')

