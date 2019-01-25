from aiohttp import web
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
