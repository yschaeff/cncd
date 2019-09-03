# How to INSTALL

Here are some notes I made during installation on a Raspberry Pi. Please review
them carefully and make sure you understand each step.

## Install Raspbian

Assuming you don't have an operating system installed yet we can install Raspbian
on the RPI.

- Download and install Raspbian
  - Download at https://www.raspberrypi.org/downloads/raspbian/
  - dd if=debian.img of=/dev/sdX

- For a headless Pi make an empty file called 'ssh' in the boot partition of the SD card.
    - pmount /dev/sdbX1
    - touch /media/sdX1/ssh
    - pumount /dev/sdbX1
- Alternatively when you have a screen 

- Boot rPI and attach screen & keyboard (user/pass: pi/raspberry)
  - Make the rPI accessable over the network:
  - sudo systemctl enable ssh.service
  - sudo systemctl start ssh.service
  - note its IP address: ip addr
  - Disconnect screen and keyboard

I would advice to create a user for yourself with sudo rights and delete the pi
user. You do not have to but since we are connecting this thing to the Internet
you MUST ABSOLUTELY change your password! Copy your public ssh key to your user
so we can enable password less login.

- Log in to the pi via ssh and create a new user
  - ssh pi@10.0.0.29
  - sudo groupadd cnc-operators
  - sudo useradd -m -G sudo,cnc-operators -s /bin/bash MY_USER_NAME
  - sudo passwd MY_USER_NAME
  - sudo reboot

- Trash pi user.
  - ssh-copy-id MY_USER_NAME@10.0.0.29
  - ssh MY_USER_NAME@10.0.0.29
  - sudo userdel -r pi
  - sudo rm /etc/sudoers.d/010_pi-nopasswd

## Setup dependencies

Now we create a user called 'cnc' which will run CNCD and make sure we give it
access to the serial ports. We also copy the authorized_keys file from our user
above so later the client software can log in without a password prompt.

- make system user cnc and disable password auth
  - sudo vi /etc/ssh/sshd_config
    - DELETE: #PasswordAuthentication yes
    - ADD     PasswordAuthentication no
  - sudo useradd -rM -G dialout,gpio -s /bin/bash cnc

CNCD doesn't have much direct dependencies. We will install them and also 
finally checkout CNCD itself.

- Install all required software
  - sudo apt update
  - sudo apt upgrade
  - sudo apt install git python3-pip python3-serial python3-rpi.gpio
  - sudo pip3 install pyserial-asyncio

  - sudo mkdir /var/lib/gcode
  - sudo chown cnc:cnc-operators /var/lib/gcode
  - sudo chmod g+ws /var/lib/gcode
  - sudo mkdir /opt/cncd
  - sudo chown $(whoami) /opt/cncd/
  - git clone https://github.com/yschaeff/cncd.git /opt/cncd/

## Server Configuration

Now we configure the system to make sure CNCD gets started at boot time.
Additionally we use UDEV to make sure our printer/cnc device always gets
assigned the same TTY. This is recommended especially when you are connecting
multiple devices to your machine. E.g. two devices could have a race which
get assigned /dev/ttyACM0 and which /dev/ttyACM1.

- Configure CNCD
  - sudo cp ~cnc/cncd/contrib/cncd.service /lib/systemd/system/
  - sudo cp ~cnc/cncd/contrib/99-usb-serial.rules /etc/udev/rules.d/
  - sudo cp ~cnc/cncd/cncd.conf /etc/
  - edit the above 3 files to your liking, See below for configuration examples.
  - sudo systemctl enable cncd
  - sudo systemctl start cncd

By default CNCD does not listen on a network interface for security reasons.
We can however leverage the power of SSH to tunnel the Unix Domain Socket to
our local machine where we will run the client software.

To test our setup we forward the socket and connect to it using netcat. For
example in my case.

- ssh -L /tmp/cncd.sock:/var/run/cncd/cncd.sock -N cnc@10.0.0.29
- nc -U /tmp/cncd.sock

You should see a greeting messages from CNCD. There are many tricks we can do
with SSH. E.g. when the machine is not directly accessible from the internet
but another machine on the network is. We can use it as a jump host

- ssh -J <JUMPHOST_IP> -L /tmp/cncd.sock:/var/run/cncd/cncd.sock -nNT cnc@10.0.0.90

## Client Configuration

The client configuration is quite minimal it only needs to know where and how
to connect. A config file (copy to ~/.config/cnc.conf) could look like this:

```ini
[default]
unix_socket = /var/run/cncd/cncd.sock

[rpi]
shell_pre = "/usr/bin/ssh -L %(unix_socket)s:/var/run/cncd/cncd.sock -nNT cnc@10.0.0.29"
shell_post = "/bin/rm -f %(unix_socket)s"
unix_socket = /tmp/cncd-rpi.sock
```

In this case when the client, cnc-tui.py (I symlinked it at /usr/local/bin/cnc)
is run without arguments it will try to connect to a local unix socket, When
run as 'cnc-tui.py rpi' it will setup a tunnel to that configured device first.

To transfer files you can use any method you like to get your gcode files into
the gcode directory we created earlier. Make it a SMB, NFS mount for example.
Personally I prefer rsync:

```shell
rsync -rav gcode/ cnc@10.0.0.29:~/gcode
```

## setup webcam server
  - cd /opt/cncd/contrib
  - sudo ./setup_webcams
  - sudo systemctl start webcam0.service ##(and others)

## example configuration:

### UDEV

This rule is to make sure my printer gets assigned the same TTY regardless of
any other USB serial device connected. If you have multiple machines I highly recommend
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
plugins_enabled = progress, gpio, pluginlist, data, logforward, trace, temperature, actions, shell, gcode
cnc_devices = prusa_i3, zmorph, franken_plotter
cameras = cam1

[prusa_i3]
name = Prusa i3 MK2s
port = serial:///dev/ttyACM0@115200
library = /home/cnc/gcode/i3/
firmware = marlin

[franken_plotter]
name = plotter
port = serial:///dev/ttyUSB0@115200
library = /home/cnc/gcode/plotter/
firmware = generic

[zmorph]
name = Zmorph VX
port = tcp://192.168.0.176:23
library = /home/cnc/gcode/zmorph/
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
