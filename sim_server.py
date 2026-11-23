"""A small MCP stdio server. The scene, actions and units are deliberately synthetic."""
import argparse
import base64
from hashlib import sha256
import json
from pathlib import Path
import struct
import sys
import time
import zlib


def png(cells):
    """Draw a four-cell rail: blue hand, red puck, green destination."""
    width, height = 160, 56
    hand, puck, goal = cells
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            cell = x // 40
            color = (26, 36, 55) if cell % 2 == 0 else (41, 52, 72)
            if cell == goal and y >= 44:
                color = (51, 205, 142)
            if cell == hand and 5 < y < 13 and 6 < x % 40 < 34:
                color = (104, 175, 255)
            if cell == puck and (x % 40 - 20) ** 2 + (y - 32) ** 2 < 80:
                color = (255, 103, 102)
            raw.extend(color)

    def chunk(name, data):
        return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data) & 0xffffffff)

    header = struct.pack(">2I5B", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


ACTIONS = ("left", "right", "grasp", "release")
TOOLS = [
    {"name": "observe", "description": "Inspect the rail state and its synthetic RGB image.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "act", "description": "Apply one simulator action at the observed revision. Inspect the new observation.",
     "inputSchema": {"type": "object", "properties": {"action": {"enum": list(ACTIONS)},
         "revision": {"type": "integer", "minimum": 0}}, "required": ["action", "revision"], "additionalProperties": False}},
    {"name": "finish", "description": "End the episode and check whether the puck is resting on the goal.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
]


class Episode:
    def __init__(self, audit):
        self.audit = audit
        self.hand, self.puck, self.goal = 0, 1, 3
        self.held = self.closed = False
        self.revision = 0

    def call(self, tool, args):
        if self.closed:
            raise ValueError("Episode closed")
        if not isinstance(args, dict):
            raise ValueError("Arguments must be an object")
        if tool in ("observe", "finish"):
            if args:
                raise ValueError("Unexpected arguments")
        elif tool == "act":
            if set(args) != {"revision", "action"} or type(args["revision"]) is not int or args["revision"] != self.revision:
                raise ValueError("Read the latest observation before acting")
            action = args["action"]
            if action not in ACTIONS or self.revision >= 16:
                raise ValueError("Unknown action or action budget reached")
            if action in ("left", "right"):
                target = self.hand + (1 if action == "right" else -1)
                if not 0 <= target <= 3:
                    raise ValueError("End of rail")
                self.hand = target
                if self.held:
                    self.puck = target
            elif action == "grasp":
                if self.held or self.hand != self.puck:
                    raise ValueError("Cannot grasp here")
                self.held = True
            else:
                if not self.held:
                    raise ValueError("Hand empty")
                self.held = False
            self.revision += 1
        else:
            raise ValueError("Unknown tool")
        self.closed = tool == "finish"
        state = dict(hand=self.hand, puck=self.puck, goal=self.goal, held=self.held, revision=self.revision)
        if self.closed:
            state["success"] = self.puck == self.goal and not self.held
        frame = png((self.hand, self.puck, self.goal))
        record = dict(t=time.monotonic(), tool=tool, args=args, state=state, image_sha256=sha256(frame).hexdigest())
        if self.audit:
            self.audit.write(json.dumps(record) + "\n")
            self.audit.flush()
        content = [{"type": "text", "text": json.dumps(state)}]
        if not self.closed:
            content.append({"type": "image", "mimeType": "image/png", "data": base64.b64encode(frame).decode("ascii")})
        return {"content": content}


def serve(episode):
    for line in sys.stdin:
        request_id = None
        try:
            req = json.loads(line)
            request_id = req.get("id")
            if request_id is None:
                continue
            method = req["method"]
            params = req.get("params", {})
            if method == "initialize":
                supported = ("2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25")
                version = params.get("protocolVersion")
                result = {"protocolVersion": version if version in supported else supported[-1],
                          "capabilities": {"tools": {}}, "serverInfo": {"name": "robopilot-sim", "version": "1.0"}}
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": TOOLS}
            elif method == "tools/call":
                try:
                    result = episode.call(params["name"], params.get("arguments", {}))
                except ValueError as exc:
                    result = {"isError": True, "content": [{"type": "text", "text": str(exc)}]}
            else:
                print(json.dumps({"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Unknown method"}}), flush=True)
                continue
            response = {"jsonrpc": "2.0", "id": request_id, "result": result}
        except (ValueError, KeyError, TypeError, AttributeError):
            response = {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32600, "message": "Invalid request"}}
        print(json.dumps(response), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", type=Path)
    args = parser.parse_args()
    if args.audit:
        # A reconnect cannot silently reset the world under the same episode ID.
        with args.audit.open("x", encoding="utf-8") as audit:
            serve(Episode(audit))
    else:
        serve(Episode(None))
