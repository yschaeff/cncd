# CNCD

Control your 3D printer farm safely over the Internet.

![Logo](https://github.com/yschaeff/cncd/raw/master/images/cncd.png)

CNCD allows you to manage and operate your 3D printers and other GCODE accepting
devices remotely. Modest hardware (like a Raspberry Pi Zero) is easily capable
of driving multiple printers simultaneously.

## Features
- Client/Server model, serving many clients at the same time.
- Start jobs remotely
- Safe for the internet
- Plugin support
- Light weight and fast!

CNCD is designed to be agnostic of the type of CNC device. While primaraly tested on 3D printers any GCODE accepting device such as plotters, laser cutters or routers should be supported. CNCD is as bare bones as possible with extra functionality modular implemented as plugins.

## Current Plugins
- Manual operation (move, preheat, etc), custom GCODE injection.
- Control GPIOs on RaspberryPi.
- Temperature monitoring.
- Live progress monitoring with respect to Z-height, filesize, and extrusion length.
- Precooked actions exposed to User Interface.
- Custom shell commands (e.g. Enable webcam server)

The sever side software has no User Interface (think of it like a webserver) and should be able to support any client UI. The reference implementation for a clients is terminal based (TUI).

![Screenshot](https://github.com/yschaeff/cncd/raw/master/images/cnc-screenshot2.png)

An experimental web client exists but is not actively worked on. Contributions to this client are especially welcome.

![Screenshot](https://github.com/yschaeff/cncd/raw/master/images/cnc-httpd-screenshot.png)


