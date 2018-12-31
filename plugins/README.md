# Plugins

## Enable and configure plugins

To use a plugin place it in the folder denoted by the "plugin_path" property
from the cncd.conf. Next add the plugin name (filename without the .py extension to "plugins_enabled". This is a comma separated list of plugins.

Some plugins require an additional configuration section in
the cncd.conf file (see the accompanying <plugin>.md text file). Restart or
reload CNCD to load the plugin.

## Plugin workings

A plugin can augment CNCD in 3 ways:

    1. Register new commands which can be executed by a user interface.
    2. Register hooks in CNCD's code. For example get notified when a new connection is made.
    3. Register actions. Actions are precooked commands which will be advertised to an user interface. The UI can display the actions and send the commands on user request. It does not need to know about the specifics of the command.

## Writing your own plugin.

A plugin MUST have a class called Plugin and it is strongly advised that it
inherits from the SkeletonPlugin (pluginskel.py). If at a later date some
required property is added to the plugins your plugin likely keeps working
without modification. For the same reason, if you overwrite the __init__()
function make sure to call super.__init__().

A plugin MUST define NAME, PREHOOKS, POSTHOOKS, PLUGIN_API_VERSION, HANDLES, ACTIONS. At startup the plugins are instantiated. You are allowed to define the above properties at __init__() but not later.

Init gets passed a datastore and gctx. More on those later in this document.

### Costum command handlers

The simplest functionality to implement is one or multiple handlers. HANDLES MUST be a list of strings. Each string MUST NOT contain spaces. When receiving a command from the user which is equal to one of the strings in HANDLES the following function from the plugin will be called:

    async def handle_command(self, gctx, cctx, lctx)

CNCD uses asyncio for asynchronous cooperative multitasking. This means that any function should hand back control to the scheduler in a timely fashion. You are allowed to do long running operations in handle_command but make sure the function yields regularly by for example calling

    await asyncio.sleep(0)

handle_command gets passed 3 arguments:

 1. lctx. Local context. Data valid during the execution of the command. it
    contains lctx.writeln() to pass data back to the client and lctx.argv, the
    precise command the UI issues.
 2. cctx. Connection context. Data valid during the whole connection from the
    client. It includes the client socket. (dict)
 3. gctx. Global context. Data shared with the entire program. Also a dict.
    Contains a parsed configuration, listeng sockets and generally all 
    instatiated object used in the program.

### Datastore

Available to the plugins is a datastore. Plugins are allow to read and write from and to it. It is meant to share data with client and other plugins. For example a temperature plugin may store the latest temperature for each device in the datastore, other plugins as well as the client can read it.

Plugins are not supposed to store private information in the datastore. Any internal state they should keep to themselves.

### Code hooks

A plugin could also request to be called when executing certain code. The hooks in PREHOOKS will be called just before executing the hooked code and the POSTHOOKS directly after.

Both properties are dicts where the key is a tuple containing the module of the hook and the function. The item is a list of functions to be called. Those functions should have the same signature as the hooked function.

    ('robot', 'Device.gcode_open_hook'):[self.open_cb]

Try not to do any complex tasks in these functions since it might introduce a noticeable delay to the user of execution takes to long.

### Actions

ACTIONS may contain Action instances. An action consist of a command with arguments, a label, and a description. All three are regular strings.
Actions enable a user interface to offer precooked commands to the user without the need to implement specific functionality of that plugin.

