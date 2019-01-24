from aiohttp import web
import asyncio
import aiohttp_jinja2

async def cncd_request(func):
    event = asyncio.Event()
    data = []
    def receive(lines):
        data.extend(lines)
        event.set()
    func(receive)
    await event.wait()
    return data


@aiohttp_jinja2.template('index.html')
async def index(request):
    controller = request.app['controller']
    data = await cncd_request(controller.get_devlist)

    print(dir(request))
    print(data)
    
    return {'devices': data}

@aiohttp_jinja2.template('index.html')
async def device_view(request):
    controller = request.app['controller']
    data = await cncd_request(controller.get_devlist)

    print(data)
    
    return {'devices': data}
