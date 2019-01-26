from aiohttp import web, WSMsgType
from functools import partial
import asyncio
import aiohttp_jinja2

async def cncd_request(func):
    event = asyncio.Event()
    data = {}
    def receive_cb(response):
        data.update(response)
        event.set()
    func(receive_cb)
    await event.wait()
    #print(func)
    #print(data)
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

async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    device = request.match_info['device']

    def cb(msg):
        asyncio.ensure_future(ws.send_json(msg))
        print(msg)
    controller = request.app['controller']
    controller.subscribe(cb, device)

    async for msg in ws:
        if msg.type == WSMsgType.ERROR:
            print('ws connection closed with exception %s' %
                  ws.exception())
            continue
        if msg.type != WSMsgType.TEXT:
            continue
        if msg.data == 'close':
            await ws.close()
            continue
        ## finally handle the request
        print("received: " + msg.data)
        #await ws.send_str(msg.data + '/answer')
        await action(request, msg.data, device)

    print('websocket connection closed')
    controller.unsubscribe(cb, device)
    return ws
