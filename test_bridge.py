import asyncio
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, Mock

from pilot import check, workspace
from sim_server import Episode
from run_client import acp, stream

ROOT = Path(__file__).resolve().parent


class BridgeTests(unittest.TestCase):
    def test_full_stdio_episode(self):
        with TemporaryDirectory() as temp:
            path = Path(temp)
            req = [{"id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
                   {"method": "notifications/initialized"}, {"id": 2, "method": "tools/list"}]
            calls = [("observe", {})] + [("act", {"action": action, "revision": i})
                      for i, action in enumerate(["right", "grasp", "right", "right", "release"])] + [("finish", {})]
            for n, (tool, args) in enumerate(calls, 3):
                req.append({"id": n, "method": "tools/call", "params": {"name": tool, "arguments": args}})
            wire = "".join(json.dumps({"jsonrpc": "2.0", **r}) + "\n" for r in req)
            response = subprocess.run([sys.executable, str(ROOT / "sim_server.py"), "--audit", str(path / "events.jsonl")],
                                      input=wire, capture_output=True, text=True, check=True, timeout=10)
            replies = [json.loads(line) for line in response.stdout.splitlines()]
            self.assertEqual(len(replies), len(req) - 1)
            self.assertEqual([t["name"] for t in replies[1]["result"]["tools"]], ["observe", "act", "finish"])
            self.assertEqual(replies[2]["result"]["content"][1]["mimeType"], "image/png")
            self.assertTrue(json.loads(replies[-1]["result"]["content"][0]["text"])["success"])
            self.assertEqual(check(path), 0)

    def test_stale_and_closed(self):
        e = Episode(None)
        e.call("act", {"action": "right", "revision": 0})
        with self.assertRaises(ValueError):
            e.call("act", {"action": "right", "revision": 0})
        self.assertEqual(e.hand, 1)
        e.call("finish", {})
        with self.assertRaises(ValueError):
            e.call("act", {"action": "grasp", "revision": 1})

    def test_configs_with_spaces(self):
        import tomllib
        with TemporaryDirectory(prefix="rail demo ") as temp:
            for provider in ("codex", "antigravity", "cursor"):
                path = Path(temp) / provider
                config = workspace(provider, path).read_text(encoding="utf-8")
                data = tomllib.loads(config)["mcp_servers"] if provider == "codex" else json.loads(config)["mcpServers"]
                self.assertEqual(data["rail"]["args"][-1], str(path.resolve() / "events.jsonl"))
                with self.assertRaises(FileExistsError):
                    workspace(provider, path)


class TransportTests(unittest.IsolatedAsyncioTestCase):
    def client(self, *events):
        client = Mock()
        client.stdout = asyncio.StreamReader()
        for event in events:
            client.stdout.feed_data((json.dumps(event) + "\n").encode())
        client.stdout.feed_eof()
        client.stdin.drain = AsyncMock()
        client.wait = AsyncMock(return_value=0)
        return client

    async def test_stream_terminals(self):
        codex = self.client({"type": "turn.started"}, {"type": "turn.completed"})
        await stream(codex, "codex")
        codex.wait.assert_awaited_once()
        agy = self.client({"event": "result", "result": {"status": "SUCCESS"}})
        await stream(agy, "antigravity")
        self.assertEqual(json.loads(agy.stdin.write.call_args.args[0])["event"], "user")

    async def test_stream_failure_and_eof(self):
        for provider, events in [
            ("codex", [{"type": "turn.failed"}]), ("codex", []),
            ("antigravity", [{"event": "result", "result": {"status": "ERROR"}}]),
        ]:
            with self.subTest(provider=provider, events=events), self.assertRaises(RuntimeError):
                await stream(self.client(*events), provider)

    async def test_acp_interleaved_requests(self):
        client = self.client(
            {"id": 1, "result": {}}, {"id": 2, "result": {}},
            {"id": 3, "result": {"sessionId": "sim", "models": {"currentModelId": "test"}}},
            {"method": "session/update", "params": {"update": {}}},
            {"id": 90, "method": "session/request_permission"},
            {"id": 4, "result": {"stopReason": "end_turn"}})
        server = {"command": "python", "args": ["sim_server.py"]}
        await acp(client, ROOT, "test", server)
        sent = [json.loads(call.args[0]) for call in client.stdin.write.call_args_list]
        self.assertEqual([msg["method"] for msg in sent[:4]],
                         ["initialize", "authenticate", "session/new", "session/prompt"])
        self.assertEqual(sent[2]["params"]["mcpServers"][0]["args"], server["args"])
        self.assertEqual(sent[-1]["result"]["outcome"]["outcome"], "cancelled")

    async def test_acp_error(self):
        client = self.client({"id": 1, "error": {"code": -32601}})
        with self.assertRaisesRegex(RuntimeError, "initialize"):
            await acp(client, ROOT, "test", {})


if __name__ == "__main__":
    unittest.main()
