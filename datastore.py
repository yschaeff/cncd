from collections import defaultdict
from functools import partial
from pluginmanager import plugin_hook

## The datastore can be used by anyone, including plugins to store information.
## Reasonable contents is data to be communicated to the user at some point. 
## Such as progress or temparature per device.
## convention: keys are either the handles of the cnc devices or 'global'.
## Other values are allowed such as plugin specific data

class DataStore:
    def __init__(self):
        self.devicedata = defaultdict(partial(defaultdict, str))
        self.globaldata = defaultdict(str)

    @plugin_hook
    async def update_device(self, devicename, name, value):
        self.devicedata[devicename][name] = value
    def get_device(self, devicename, name):
        return self.devicedata[devicename][name]

