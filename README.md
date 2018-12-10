# CNCD

*WARNING, HERE BE DRAGONS: This is very much an alpha product. Stupid bugs are
likely still present.  If you are neither the Adventurous type, Python
developer, or Commandline Masochist, your are better off leaving the project to
mature some more.*

![Logo](https://github.com/yschaeff/cncd/raw/master/logo/cncd.png)

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

### DO not read further, these are not the instructions you are looking for.

HOWTO

Download at https://www.raspberrypi.org/downloads/raspbian/

unzip
dd

## Attach screen and login (pi/raspberry)
sudo useradd -m yuri -s /bin/bash
sudo usermod -aG sudo yuri
sudo passwd yuri
sudo apt update
sudo apt install ssh
sudo systemctl enable ssh.service
sudo systemctl start ssh.service
ip addr
logout

## on remote system
ssh-copy-id yuri@10.0.0.29
ssh yuri@10.0.0.29
sudo userdel -r pi
sudo vi /etc/ssh/sshd_config
    <<< PasswordAuthentication no
    >>> #PasswordAuthentication yes
sudo useradd -r -m -G tty -s /bin/bash cnc
sudo cp -r .ssh/ ~cnc/
sudo chown -R cnc:cnc ~cnc/.ssh/
sudo apt-install git

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



