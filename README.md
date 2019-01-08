# CNCD

*WARNING, HERE BE DRAGONS: This is very much an alpha product. Stupid bugs are
likely still present.  If you are neither the Adventurous type, Python
developer, or Commandline Masochist, your are better off leaving the project to
mature some more.*

*DISCLAIMER: This README does contain some amount of Octoprint bashing. I
in fact love Octoprint, and appreciate what Gina has done for the 3D printer
community. Consider watching Octoprint on air and support the project via
Patreon. Octoprint (and its limitations) is the reason and inspiration me to
write this software.*

*DISCLAIMER 2: I present this software as an octoprint alternative. In practice
Octoprint handles hunderdths of configurations and corner cases. I only tried
and tested *my configuration*. It might not work for you yet.*

![Logo](https://github.com/yschaeff/cncd/raw/master/images/cncd.png)

CNCD (which stands for CNC Daemon) is server software
to control CNC devices and manage them remotely. It aims to control any CNC
device (e.g. 3D printer, router, laser cutter) that accepts GCODE commands via
its serial port or TCP socket.

It is designed to run on a Linux host, specifically a Raspberry Pi single
board computer running Raspbian. However any similar OS with Python version 3.5
or beyond and the required python dependencies should work.

## features
- Light weight, instant startup.
- Supports multiple CNC devices running simultaneously.
- Support multiple webcams.
- Allows multiple clients to connect and control devices.
- Pause/resume operation
- Safe for the Internet.
- Plugin support

## non-features
I.e. the thing we purposely do NOT support.

- No encryption, authentication or user management.
- No GCODE file management. (upload, delete, etc)
- No TCP support.
- No webcam support
- No serial port auto discovery.
- No interface for humans, no webserver.

## Your features and non-features conflict!

You are absolutely right. Allow me to explain some of them.

### "Safe for the Internet" vs. "No encryption or Authentication"
This is a big one and comes from the fact that the Octoprint developer calls
for **not** connecting Octoprint to the Internet. I get why. I would not lightly
trust my own software enough to expose it to remote hackers. Especially when controlling
physical machines. Though this is exactly what many people use Octoprint for.

My solution is not to do any authentication because Linux already does that. Not
do any encryption because ssh already does that. CNCD will listen for commands
on a *Unix domain socket*. This means it is not accessible over the network. And it
is not even accessible by other users on the same system, If you want to access
your CNC device remotely you can use ssh to forward the socket to your local
system. With password authentication disabled ssh is considered *very* secure.

Thus, although technically trivial CNCD does not support TCP by design!

### Light weight
The reason I started this project is that I noticed in the first 10 minutes of startup
Octoprint took at least 10 minutes of CPU time on an rPI2. Which I just can't
explain. Open the serial port and jam some gcode in it. How hard can it be?

In comparison. CNCD takes about 3 seconds to start on an rPI1 (mostly due to
a slow SD card).

I do like to keep things as simple as possible. Though I did implement a plugin
system. This complicates the design but in a recent Octoprint on air
episode Gina mentioned the plugin system in Octoprint actually helps to reduce
code complexity over time!

### Multiple CNC device support
CNCD is designed from the ground up to support and operate multiple CNC devices
simultaneously. It tries to be agnostic about the nature of the CNC device. It should
be able to operate a CNC router as well as a 3D printer as well as a laser cutter.
As long as they accept commands over the serial port or a TCP socket.

### No file management
There is deliberately no code to manage your gcode collection. Just a pointer
to where your files are stored. Want to send files to your printer? Use rsync,
samba, nfs, or use your imagination.

### No GUI
We don't run a webserver or any other form of GUI. We just open
a socket and wait for other software to send us commands. The protocol is ASCII
and line based so you could totally use netcat if you are *that* kind of person.

That being said the software it not very useful without anyone writing a client
for it to connect with. Since nobody else did that yet I wrote an ncurses based
client. Available on this same repository in ./frontends/ directory.

![Screenshot](https://github.com/yschaeff/cncd/raw/master/images/cnc-screenshot.png)

Contributions on the GUI side are especially welcome!

### No webcam support / multiple webcam support
Webcam support is similar to what Octoprint does. Don't manage them but just
pass the URL to the GUI to do whatever. Except for us there is no practical limitation
on the number of webcams.

## Screenshots please?

What? No you don't unders^C...Urgh. Fine.

![Screenshot](https://github.com/yschaeff/cncd/raw/master/images/cncd-screenshot.png)

# How to INSTALL

These instructions are for advanced users and not meant to be followed by the
letter. It is just how I would do it, roughly. Please consider them carefully.

- Download and install Raspbian
  - Download at https://www.raspberrypi.org/downloads/raspbian/
  - dd if=debian.img of=/dev/sdX
- Boot rPI and attach screen & keyboard (user/pass: pi/raspberry)
  - Make the rPI accessable over the network:
  - sudo systemctl enable ssh.service
  - sudo systemctl start ssh.service
  - note its IP address: ip addr
  - Disconnect screen and keyboard
- Log in to the pi via ssh and create a new user
  - ssh pi@10.0.0.29
  - sudo useradd -m -G sudo -s /bin/bash MY_USER_NAME
  - sudo passwd MY_USER_NAME
  - sudo reboot
- Trash pi user. IMPORTANT!
  - ssh-copy-id MY_USER_NAME@10.0.0.29
  - ssh MY_USER_NAME@10.0.0.29
  - sudo userdel -r pi
  - sudo rm /etc/sudoers.d/010_pi-nopasswd
- make system user cnc and disable password auth
  - sudo vi /etc/ssh/sshd_config
    - DELETE: #PasswordAuthentication yes
    - ADD     PasswordAuthentication no
  - sudo useradd -r -m -G dialout,gpio -s /bin/bash cnc
  - sudo cp -r .ssh/ ~cnc/
  - sudo chown -R cnc:cnc ~cnc/.ssh/
- Install all required software
  - sudo apt update
  - sudo apt upgrade
  - sudo apt install git python3-pip python3-serial python3-rpi.gpio
  - sudo pip3 install pyserial-asyncio
  - sudo -i -u cnc
    - git clone https://github.com/yschaeff/cncd.git cncd
    - mkdir gcode
    - exit
- Configure CNCD
  - sudo cp ~cnc/cncd/contrib/cncd.service /etc/systemd/system/
  - sudo cp ~cnc/cncd/contrib/99-usb-serial.rules /etc/udev/rules.d/
  - sudo cp ~cnc/cncd/cncd.conf /etc/
  - edit the above 3 files to your liking, See below for my configuration.
  - sudo systemctl enable cncd
  - sudo systemctl start cncd

From your local machine you can now setup a ssh tunnel. for example on my 
local network:

- ssh -L /tmp/cncd.sock:/var/run/cncd/cncd.sock -M cnc@10.0.0.29

You can now use the TUI to connect!

And to transfer files:
- rsync -rav gcode/ cnc@10.0.0.29:~/gcode

## example configuration:

### UDEV

This rule is to make sure my printer gets assigned the same TTY regardless of
any other USB serial device connected. If you have multiple machines I highly recomment
this. Figure out the correct setting with lsusb and udevadm

```udev
SUBSYSTEM=="tty", ATTRS{idVendor}=="2c99", ATTRS{idProduct}=="0001", ATTRS{serial}=="CZPX2017X003XK19721", SYMLINK+="ttyPRUSA_i3"
```

### SYSTEMD

Make sure is always runs as unprivileged user cnc and the dir /var/run/cncd/ gets
created before start. (the cnc user is not allowed to do this itself)

```ini
[Unit]
Description=CNC Daemon

[Service]
ExecStart=/home/cnc/cncd/cncd.py
User=cnc
Group=cnc
RuntimeDirectory=cncd
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

### CNCD config

```ini
[general]
unix_socket = /var/run/cncd/cncd.sock
log_level = warning
plugin_path = /home/cnc/cncd/plugins
plugins_enabled = progress, gpio, pluginlist, data, logforward, trace, temperature, actions, shell
cnc_devices = prusa_i3, zmorph, franken_plotter
cameras = cam1

[prusa_i3]
name = Prusa i3 MK2s
port = serial:///dev/ttyACM0@115200
library = ./gcode/
firmware = marlin

[franken_plotter]
name = plotter
port = serial:///dev/ttyUSB0@115200
library = ./gcode/
firmware = generic

[zmorph]
name = Zmorph VX
port = tcp://192.168.0.176:23
library = /home/yuri/repo/3d-models/zmorph/printer/
firmware = smoothie

[cam1]
name = Okki
url = http://10.0.0.90:8080/?action=stream

## PLUGIN SPECIFIC CONFIGURATION ##

## TEMPERATURE ##

[temperature]
blacklist = plotter, foo

## GPIO ##

[gpio]
mode = board
pins = relay, button

[relay]
pin = 7
mode = output
label = Relay
description = This relay switches both the light and the Prusa printer.
export = True

[button]
pin = 4
mode = input
pud = up
action = gpio 7 -1
edge = falling

## SHELL ##

[shell]
# These commands are explicity configured in /etc/sudoers
start webcam = sudo systemctl start videoC270.service
stop webcam = sudo systemctl stop videoC270.service
```

### CNC Config (client)

The TUI client can be found in the frontends directory and started with ./cnc.py. I suggest making a softlink to it in /usr/local/bin/. For example '''sudo /home/yuri/repo/cncd/frontend/cnc.py -s cnc'''
It accepts a -c parameter for the configuration file. If not specified it will try
'~/.config/cnc.conf'. It will also accept the name of CNCD instance if configured.

''' vi ~/.config/cnc.conf '''

'''ini
## Default instance to connect to
[default]
unix_socket = /home/yuri/repo/cncd/.cncd.sock

[okki]
shell_pre = "/usr/bin/ssh -L %(unix_socket)s:/var/run/cncd/cncd.sock -nNT cnc@10.0.0.34 -p 22"
shell_pre_sleep = 1
shell_post = "/bin/rm -f %(unix_socket)s"
unix_socket = /tmp/cncd.sock
'''

To connect to the remote client above type: '''cnc okki'''
The unix domain socket will be tunneled over SSH giving you a secure connection
to CNCD.
