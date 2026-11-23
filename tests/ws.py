#!/usr/bin/env python3
"""Synthetic protocol and persistence check; Python standard library only."""
import base64
import hashlib
import json
import os
import pathlib
import socket
import struct
import sys
import time

def read_exact(stream, count):
    result = bytearray()
    while len(result) < count:
        chunk = stream.read(count - len(result))
        if not chunk:
            raise RuntimeError("Unexpected WebSocket EOF")
        result.extend(chunk)
    return bytes(result)

def frame(sock, payload, opcode=1):
    mask = os.urandom(4)
    size = len(payload)
    if size < 126:
        head = bytes((128 | opcode, 128 | size))
    elif size < 65536:
        head = bytes((128 | opcode, 254)) + struct.pack("!H", size)
    else:
        head = bytes((128 | opcode, 255)) + struct.pack("!Q", size)
    sock.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

def response(sock, stream, correlation):
    while True:
        a, b = read_exact(stream, 2)
        if b & 128:
            raise RuntimeError("Server frames must not be masked")
        length = b & 127
        if length == 126:
            length = struct.unpack("!H", read_exact(stream, 2))[0]
        elif length == 127:
            length = struct.unpack("!Q", read_exact(stream, 8))[0]
        if length > 1024 * 1024:
            raise RuntimeError("Unexpected oversized test response")
        payload = read_exact(stream, length)
        opcode = a & 15
        if opcode == 9:
            frame(sock, payload, 10)
            continue
        if opcode != 1 or not a & 128:
            raise RuntimeError("Unexpected WebSocket frame")
        value = json.loads(payload)
        if value.get("corrId") == correlation:
            return value["resp"]

mode = sys.argv[1]
host = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1"
if mode == "unreachable":
    socket.gethostbyname(host)
    try:
        with socket.create_connection((host, 5225), timeout=3):
            pass
    except (OSError, TimeoutError):
        print("Bridge peer cannot reach the loopback listener.")
        raise SystemExit(0)
    raise SystemExit("Control socket unexpectedly reachable over the bridge")

deadline = time.monotonic() + 60
while True:
    try:
        sock = socket.create_connection((host, 5225), timeout=5)
        break
    except OSError:
        if time.monotonic() >= deadline:
            raise SystemExit("Control socket did not start")
        time.sleep(1)
listeners = []
for table in ("/proc/net/tcp", "/proc/net/tcp6"):
    for line in pathlib.Path(table).read_text().splitlines()[1:]:
        fields = line.split()
        if fields[3] == "0A" and fields[1].endswith(":1469"):
            listeners.append(fields[1])
assert listeners == ["0100007F:1469"], "Control listener is not IPv4 loopback only"
sock.settimeout(10)
with sock:
    key = base64.b64encode(os.urandom(16)).decode()
    request = ("GET / HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\n"
               "Connection: Upgrade\r\nSec-WebSocket-Version: 13\r\n"
               "Sec-WebSocket-Key: " + key + "\r\n\r\n")
    sock.sendall(request.encode())
    stream = sock.makefile("rb")
    status = stream.readline()
    assert b" 101 " in status, "WebSocket upgrade failed"
    headers = {}
    while (line := stream.readline()) != b"\r\n":
        assert line, "Incomplete WebSocket handshake"
        name, value = line.decode().split(":", 1)
        headers[name.lower()] = value.strip()
    expected = base64.b64encode(hashlib.sha1(
        (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
    assert headers.get("sec-websocket-accept") == expected
    def command(cmd, correlation):
        frame(sock, json.dumps({"corrId": correlation, "cmd": cmd}).encode())
        return response(sock, stream, correlation)
    user = command("/u", "test-user")
    assert user["type"] == "activeUser"
    assert user["user"]["profile"]["displayName"] == "simplex"
    if mode == "write":
        changed = command("/profile simplex synthetic-persistence-marker", "test-profile")
        assert changed["type"] == "userProfileUpdated"
        note = command("/* synthetic-text-marker", "test-note")
        assert note["type"] == "newChatItems"
    elif mode == "read":
        assert user["user"]["profile"]["shortDescr"] == "synthetic-persistence-marker"
        chats = command("/_get chats " + str(user["user"]["userId"]), "test-chats")
        local = [c["chatInfo"]["noteFolder"]["noteFolderId"] for c in chats["chats"]
                 if c["chatInfo"]["type"] == "local"]
        assert len(local) == 1
        notes = command("/_get chat *" + str(local[0]) + " count=10", "test-notes")
        assert any(item["content"].get("msgContent", {}).get("text") == "synthetic-text-marker"
                   for item in notes["chat"]["chatItems"])
    else:
        raise SystemExit("Unknown test mode")
    frame(sock, b"", 8)
print("Synthetic WebSocket, profile and local text check passed.")
