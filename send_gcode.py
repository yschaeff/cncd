#!/usr/bin/env python3

#-p port
#-d dev
#"gcode"

from argparse import ArgumentParser
import socket, sys, random

parser = ArgumentParser()
parser.add_argument("-p", "--port", help="daemon TCP port", type=int, action="store", required=True)
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument("-l", "--list-devices", help="List devices available at remote host", action="store_true")
group.add_argument("-d", "--device", help="Device to send GCODE to. If omitted don't send GCODE but list devices instead.", action="store")
parser.add_argument("-g", "--gcode", help="gcode to execute", action="store")
args = parser.parse_args()

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

def response_is_OK(resp):
    if len(resp) < 1: return False
    line = resp[0]
    return line.strip().startswith("OK")

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    try:
        s.connect(("localhost", args.port))
    except ConnectionRefusedError as e:
        print(e)
        sys.exit(1)

    if args.list_devices:
        msg = query(s, "devlist")
        for line in msg:
            print(line)
        sys.exit(0)
    elif not args.gcode:
        # device MUST be set
        msg = query(s, "devctl '{}' status".format(args.device))
        for line in msg:
            print(line)
        sys.exit(0)

    msg = query(s, "gcode '{}' '{}'".format(args.device, args.gcode))
    for line in msg:
        print(line)
    succes = response_is_OK(msg)

    sys.exit(not succes)

