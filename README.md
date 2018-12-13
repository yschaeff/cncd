# CNCD

*WARNING, HERE BE DRAGONS: This is very much an alpha product. Stupid bugs are
likely still present.  If you are neither the Adventurous type, Python
developer, or Commandline Masochist, your are better off leaving the project to
mature some more.*

![Logo](https://github.com/yschaeff/cncd/raw/master/images/cncd.png)

CNCD (which stands for Computer Numerical Control Daemon) is server software
to control CNC devices and manage them remotely. It aims to control any CNC
device (e.g. 3D printer, router, laser cutter) that accepts GCODE commands via
its serial port.

It is designed to run on a Linux host, specifically a Raspberry Pi single
board computer running Raspbian. However any similar OS with Python version 3.5
or beyond and the required python dependencies should work.

## features
- Light weight, instant startup.
- Supports multiple CNC devices running simultaneously.
- Support multiple webcams.
- Allows multiple 'users' to connect and control devices.
- Pause/resume operation
- Safe for the Internet.

## non-features
I.e. the thing we purposely do NOT support.

- No encryption, authentication or user management.
- No GCODE file management.
- No TCP support.
- No webcam support
- No serial port auto discovery.
- No interface for humans, no webserver.

## Screenshots please?

What? No you don't unders^...Urgh. Fine.

![Screenshot](https://github.com/yschaeff/cncd/raw/master/images/cncd-screenshot.png)

### DO not read further, these are not the instructions you are looking for.

HOWTO

Download at https://www.raspberrypi.org/downloads/raspbian/

## @local
unzip
dd if=debian,img of=/dev/sdX
## @pi (attach a screen & keyboard)
sudo systemctl enable ssh.service
sudo systemctl start ssh.service
exit
## @local
ssh pi@10.0.0.29
    sudo useradd -m -G sudo -s /bin/bash yuri
    sudo passwd yuri
    sudo reboot
ssh yuri@10.0.0.29
    sudo userdel -r pi
    exit
ssh-copy-id yuri@10.0.0.29
ssh yuri@10.0.0.29
    sudo vi /etc/ssh/sshd_config
        <<< PasswordAuthentication no
        >>> #PasswordAuthentication yes
    sudo useradd -r -m -G dialout,gpio -s /bin/bash cnc
    sudo cp -r .ssh/ ~cnc/
    sudo chown -R cnc:cnc ~cnc/.ssh/
    sudo apt update
    sudo apt upgrade
    sudo apt install git python3-pip python3-serial vim python3-rpi.gpio
    sudo pip3 install pyserial-asyncio

    sudo cp cncd.service /etc/systemd/system/
    sudo cp cncd.conf /etc/
    sudo systemctl enable cncd
ssh cnc@10.0.0.29
    git clone https://github.com/yschaeff/cncd.git cncd
    mkdir run gcode
    <edit cncd.conf>
    
    ./cncd.py -c cncd.conf -l debug -L

ssh -L ./remotesock:/var/run/cncd/cncd.sock -M cnc@10.0.0.29
rsync -rav gcode/ cnc@10.0.0.29:~/gcode



## on remote system
ssh cnc@10.0.0.29
mkdir gcode
mkdir run
git clone https://github.com/yschaeff/cncd.git cncd
cd cnc
vi cncd.conf

diff --git a/cncd.conf b/cncd.conf
index f46c275..a344b2c 100644
--- a/cncd.conf
+++ b/cncd.conf
@@ -1,11 +1,11 @@
 [general]
 port = 4000
 address = localhost
-unix_socket = ./.cncd.sock
-log_level = debug
-library = ./gcode
-plugin_path = ./plugins
-plugins_enabled = demoplugin
+unix_socket = /home/cnc/run/cncd.sock
+log_level = warning
+library = /home/cnc/gcode
+plugin_path = /home/cncd/plugins
+plugins_enabled = 
 cnc_devices = cnc1,cnc2,cnc3,cnc4,cnc5
 cameras = cam1,cam2

apt upgrade
wget https://www.python.org/ftp/python/3.7.1/Python-3.7.1.tgz
gunzip Python-3.7.1.tgz 
tar -xf Python-3.7.1.tar 
cd Python-3.7.1/
./configure 
make
sudo make install



