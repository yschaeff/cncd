from aiohttp import web, WSMsgType
from functools import partial
import asyncio, sys
import aiohttp_jinja2
import logging as log

log.basicConfig()

async def cncd_request(func):
    event = asyncio.Event()
    data = {}
    def receive_cb(response):
        data.update(response)
        event.set()
    func(receive_cb)
    await event.wait()
    #log.warning(func)
    #log.warning(data)
    return data

async def get_device_list(request):
    controller = request.app['controller']
    return await cncd_request(controller.get_devlist)
async def get_camera_list(request):
    controller = request.app['controller']
    return await cncd_request(controller.get_camlist)
async def get_action_list(request):
    controller = request.app['controller']
    return await cncd_request(controller.get_actions)
async def get_device_info(request, device):
    controller = request.app['controller']
    return await cncd_request(partial(controller.get_data, device=device))


@aiohttp_jinja2.template('index.html')
async def index(request):
    devlist = await get_device_list(request)
    cameras = await get_camera_list(request)
    actions = await get_action_list(request)
    data = {}
    data.update(devlist)
    data.update(cameras)
    data.update(actions)
    return data

async def action(request, action, device):
    controller = request.app['controller']
    if action == 'connect':
        r =  await cncd_request(partial(controller.connect, device=device))
    elif action == 'disconnect':
        r =  await cncd_request(partial(controller.disconnect, device=device))
    elif action == 'start':
        r =  await cncd_request(partial(controller.start, device=device))
    elif action == 'stop':
        r =  await cncd_request(partial(controller.stop, device=device))
    elif action == 'abort':
        r =  await cncd_request(partial(controller.abort, device=device))
    elif action == 'pause':
        r =  await cncd_request(partial(controller.pause, device=device))
    elif action == 'resume':
        r =  await cncd_request(partial(controller.resume, device=device))
    else:
        ## not trusted, not sending
        pass


@aiohttp_jinja2.template('device.html')
async def device_view(request):
    device = request.match_info['device']

    devlist = await get_device_list(request)
    info = await get_device_info(request, device)

    data = {}
    data.update(devlist)
    data['info'] = info[device]
    data['device'] = device
    return data

async def subscription_handler(ws, channel, msg):
    log.warning(msg)
    ## msg is json like object
    info = msg[channel]
    await ws.send_json({'info':info})

async def websocket_handler(request):
    controller = request.app['controller']
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    device = request.match_info['device']

    channel = device
    def subscribe_cb(msg):
        if not msg: return
        task = request.app.loop.create_task(subscription_handler(ws, channel, msg))
    controller.subscribe(subscribe_cb, channel)

    async for msg in ws:
        if msg.type == WSMsgType.ERROR:
            log.warning('ws connection closed with exception %s' %
                  ws.exception())
            continue
        if msg.type != WSMsgType.TEXT:
            continue
        log.warning("received: " + msg.data)
        await action(request, msg.data, device)

    log.warning('websocket connection closed')
    controller.unsubscribe(subscribe_cb, device)
    return ws

