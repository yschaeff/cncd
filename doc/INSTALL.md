# INSTALLATION

This installation guide will help you through the installation and configuration
of CNCD on a Raspberry Pi. Advances users may wish to use this as a guideline
rather than _the one definitive way_. It is assumed the user performs installation
from a Linux like environment. 

A Raspberry Pi is in no way a requirement for CNCD to run. But I suspect this
will be the most common setup. Any raspberry Pi will do. Even a Raspberry Pi
Zero W is plenty powerful to run multiple devices simultaneously.

We'll break up the process in discrete parts:

 1. Prepare Raspberry Pi
 2. User management
 3. Dependencies and installation
 4. System configuration
 5. CNCD configuration
 6. Webcam installation
 7. Client configuration


## Prepare Raspberry Pi

Assuming we are starting completely from scratch you can download Raspbian at
https://www.raspberrypi.org/downloads/raspbian/.

Flash the unzipped image the usual way to your SD card

'''bash
dd if=debian.img of=/dev/sdX
'''

Now Plug the SD card in the PI and attach a monitor and a keyboard. You should
be able to log in with user 'pi' and password 'raspberry'.

If you are planning to use the PI via wifi run raspi-config to configure the
network.

'''bash
sudo raspi-config
'''

Finally note the IP address (henceforth IP_ADDR) assigned to the PI and enable
SSH access.

'''bash
ip addr
sudo systemctl enable ssh.service
sudo systemctl start ssh.service
'''

At this point you can disconnect the monitor and keyboard. If everything goes 
well we'll never again need them.


## User management

I recommend creating a system user account for CNCD and delete the pi user 
account. At the very least change its password!

Log in to the PI over SSH: '''ssh pi@IP_ADDR'''
We'll add a user of your choice (here referred to as USER) with sudo access:

'''bash
sudo useradd -m -G sudo -s /bin/bash USER
sudo passwd USER
#Now may be a good time to reboot and see if you can login with the new user
sudo reboot
'''

Now at your local machine copy your ssh keys. Later we will disable password
authentication via SSH on the PI!

'''bash
ssh-copy-id USER@IP_ADDR
#then login:
ssh USER@IP_ADDR
#now lets delete the pi user
sudo userdel -r pi
#optionally remove sudo rules for pi
sudo rm /etc/sudoers.d/010_pi-nopasswd
#


- Trash pi user. IMPORTANT!


## Dependencies and installation
## System configuration
## CNCD configuration
## Webcam installation
## Client configuration
