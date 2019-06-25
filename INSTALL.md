# How to INSTALL

Here are some notes I made during installation on a Raspberry Pi. Please review
them carefully and make sure you understand each step.

## Install Raspbian

Assuming you don't have an operating system installed yet we can install Raspbian
on the RPI. 

- Download and install Raspbian
  - Download at https://www.raspberrypi.org/downloads/raspbian/
  - dd if=debian.img of=/dev/sdX

- Boot rPI and attach screen & keyboard (user/pass: pi/raspberry)
  - Make the rPI accessable over the network:
  - sudo systemctl enable ssh.service
  - sudo systemctl start ssh.service
  - note its IP address: ip addr
  - Disconnect screen and keyboard

I advice to create a user for yourself with sudo rights and delete the pi
user. You do not have to but since we are connecting this thing to the Internet
you MUST ABSOLUTELY change your password! Copy your public ssh key to your user
so we can enable password less login.

- Log in to the pi via ssh and create a new user
  - ssh pi@10.0.0.29
  - sudo useradd -m -G sudo -s /bin/bash MY_USER_NAME
  - sudo passwd MY_USER_NAME
  - sudo reboot

- Trash pi user.
  - ssh-copy-id MY_USER_NAME@10.0.0.29
  - ssh MY_USER_NAME@10.0.0.29
  - sudo userdel -r pi
  - sudo rm /etc/sudoers.d/010_pi-nopasswd

Now we create a user called 'cnc' which will run CNCD and make sure we give it
access to the serial ports. We also copy the authorized_keys file from our user
above so later the client software can log in without a password prompt.

- make system user cnc and disable password auth
  - sudo vi /etc/ssh/sshd_config
    - DELETE: #PasswordAuthentication yes
    - ADD     PasswordAuthentication no
  - sudo useradd -r -m -G dialout,gpio -s /bin/bash cnc
  - sudo cp -r .ssh/ ~cnc/
  - sudo chown -R cnc:cnc ~cnc/.ssh/

CNCD doesn't have much direct dependencies. We will install them and also 
finally checkout CNCD itself.

- Install all required software
  - sudo apt update
  - sudo apt upgrade
  - sudo apt install git python3-pip python3-serial python3-rpi.gpio
  - sudo pip3 install pyserial-asyncio
  - sudo -i -u cnc
    - git clone https://github.com/yschaeff/cncd.git cncd
    - mkdir gcode
    - exit

Now we configure the system to make sure CNCD gets started at boot time.
Additionally we use UDEV to make sure our printer/cnc device always gets assigend
the same TTY. This is recommended especially when you are connecting multiple devices to your machine. E.g. when two devices could have a race which get assigned /dev/ttyACM0 and which /dev/ttyACM1.

- Configure CNCD
  - sudo cp ~cnc/cncd/contrib/cncd.service /lib/systemd/system/
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
