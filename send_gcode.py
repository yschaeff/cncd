#!/usr/bin/env python3

#-p port
#-d dev
#"gcode"

from argparse import ArgumentParser
import socket, sys, random

parser = ArgumentParser()
parser.add_argument("-p", "--port", help="daemon TCP port", type=int, action="store", required=True)
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument("-d", "--device", help="Device to send GCODE to. If omitted don't send GCODE but list devices instead.", action="store", type=int)
group.add_argument("-l", "--list-devices", help="List devices available at remote host", action="store_true")
parser.add_argument("gcode", help="gcode to execute", action="store")
args = parser.parse_args()

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.connect(("localhost", args.port))
except ConnectionRefusedError as e:
    print(e)
    sys.exit(1)

def readlines(s):
    buf = b""
    while True:
        buf += s.recv(1024)
        while True:
            i = buf.find(b"\n")
            if i == -1: break
            yield buf[:i+1]
            buf = buf[i+1:]

def readmsg(s, nonce):
    msg = []
    for raw in readlines(s):
        line = raw.decode()
        if not line.startswith("%d "%nonce): continue
        data = line[len("%d "%nonce):].strip()
        if data == '.':
            return msg
        msg.append(data)

def query(s, q):
    nonce = random.randint(0, 100)
    s.send("{} {}\n".format(nonce, q).encode())
    return readmsg(s, nonce)

if args.list_devices:
    msg = query(s, "dev")
    for line in msg:
        print(line)

s.close()

