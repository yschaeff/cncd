from aiohttp import web
from functools import partial
import asyncio
import aiohttp_jinja2

async def cncd_request(func):
    event = asyncio.Event()
    data = {}
    def receive(response):
        data.update(response)
        event.set()
    func(receive)
    await event.wait()
    #print(func)
    #print(data)
    return data

async def get_device_list(request):
    controller = request.app['controller']
    data = await cncd_request(controller.get_devlist)
    return data

#async def get_camera_list(request):
    #controller = request.app['controller']
    #camlist = await cncd_request(controller.get_camlist)
    #return {"xxx":"yyy"}

async def get_device_info(request, device):
    controller = request.app['controller']
    data = await cncd_request(partial(controller.get_data, device=device))
    return data


@aiohttp_jinja2.template('index.html')
async def index(request):
    devlist = await get_device_list(request)
    #cameras = await get_camera_list(request)
    #return {'devices': devlist, 'cameras':cameras}
    return {'devices': devlist}

@aiohttp_jinja2.template('device.html')
async def device_view(request):
    device = request.match_info['device']

    info = await get_device_info(request, device)
    devlist = await get_device_list(request)
    
    return {'info': info, 'devices':devlist, 'device':devlist[device]}
