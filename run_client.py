"""Run one signed-in CLI against the generated SIM workspace. No physical adapter."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import shutil
import sys
import uuid

from pilot import TASK, check, workspace


async def spawn(binary, args, cwd, env):
    return await asyncio.create_subprocess_exec(
        binary, *args, cwd=cwd, env=env, stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, stderr=None, limit=16 * 1024 * 1024)


async def send(process, message):
    process.stdin.write((json.dumps(message) + "\n").encode())
    await process.stdin.drain()


async def acp(process, work, model, server):
    """Sequential ACP requests, handling interleaved notifications and client requests."""
    seq = 0

    async def request(method, params):
        nonlocal seq
        seq += 1
        await send(process, dict(jsonrpc="2.0", id=seq, method=method, params=params))
        while line := await process.stdout.readline():
            msg = json.loads(line)
            if "method" in msg:
                if msg["method"] == "session/update":
                    update = msg.get("params", {}).get("update", {})
                    content = update.get("content", {})
                    if (update.get("sessionUpdate") == "agent_message_chunk"
                            and isinstance(content, dict)
                            and content.get("text", "").lstrip().startswith("Error: RetriableError:")):
                        raise RuntimeError("Cursor reported a retriable provider error")
                if "id" in msg:
                    reply = {"jsonrpc": "2.0", "id": msg["id"]}
                    if msg["method"] == "session/request_permission":
                        reply["result"] = {"outcome": {"outcome": "cancelled"}}
                    else:
                        reply["error"] = {"code": -32601, "message": "Unavailable"}
                    await send(process, reply)
                continue
            if msg.get("id") == seq:
                if "error" in msg:
                    raise RuntimeError("ACP rejected " + method)
                return msg["result"]
        raise RuntimeError("ACP closed before " + method)

    await request("initialize", {"protocolVersion": 1, "clientCapabilities": {
        "fs": {"readTextFile": False, "writeTextFile": False}, "terminal": False},
        "clientInfo": {"name": "robopilot", "version": "1"}})
    await request("authenticate", {"methodId": "cursor_login"})
    session = await request("session/new", {"cwd": str(work), "mcpServers": [
        {"name": "rail", **server, "env": []}]})
    actual = (session.get("models") or {}).get("currentModelId")
    print("Requested model:", model, "| ACP model:", actual or "not reported", flush=True)
    result = await request("session/prompt", {"sessionId": session["sessionId"],
        "prompt": [{"type": "text", "text": TASK}]})
    if result.get("stopReason") != "end_turn":
        raise RuntimeError("ACP stop: " + str(result.get("stopReason")))


async def stream(process, provider):
    if provider == "antigravity":
        await send(process, {"event": "user", "message": {"content": TASK}})
    else:
        process.stdin.close()
    while line := await process.stdout.readline():
        event = json.loads(line)
        if provider == "antigravity" and event.get("event") == "result":
            result = event.get("result") or {}
            if result.get("status") != "SUCCESS":
                raise RuntimeError("Antigravity terminal: " + str(result.get("status")))
            return
        if provider == "codex":
            if event.get("type") == "turn.failed":
                raise RuntimeError("Codex turn failed")
            if event.get("type") == "turn.completed":
                if await process.wait() != 0:
                    raise RuntimeError("Codex exited with an error")
                return
    raise RuntimeError("Stream ended without a successful terminal event")


async def main(args):
    executable = shutil.which(args.binary or {"codex": "codex", "antigravity": "agy", "cursor": "agent"}[args.provider])
    if not executable:
        raise SystemExit("CLI missing. Install and log in first, or supply --binary.")
    work = Path("runs").resolve() / uuid.uuid4().hex
    config = workspace(args.provider, work)
    print("SIM workspace:", work, flush=True)
    env = os.environ.copy()
    for key in ("OPENAI_API_KEY", "CODEX_API_KEY", "CURSOR_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
                "GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_GENAI_USE_VERTEXAI", "ANTHROPIC_API_KEY"):
        env.pop(key, None)
    if args.provider == "codex":
        # Process-scoped overrides also work when project config is not trusted.
        server = {"command": sys.executable, "args": [str(Path(__file__).with_name("sim_server.py").resolve()),
                                                       "--audit", str(work / "events.jsonl")]}
        flags = ["exec", "--json", "--skip-git-repo-check", "--sandbox", "read-only",
                 "-c", "mcp_servers.rail.command=" + json.dumps(server["command"]),
                 "-c", "mcp_servers.rail.args=" + json.dumps(server["args"]), "--model", args.model, TASK]
    elif args.provider == "antigravity":
        flags = ["--model", args.model, "--input-format", "stream-json", "--output-format", "stream-json"]
    else:
        # ACP registers this server explicitly in session/new. Remove the generated
        # project copy before spawning the CLI to avoid a second simulator process.
        server = json.loads(config.read_text(encoding="utf-8"))["mcpServers"]["rail"]
        config.unlink()
        flags = ["--model", args.model, "--workspace", str(work), "acp"]
    process = await spawn(executable, flags, work, env)
    try:
        run = acp(process, work, args.model, server) if args.provider == "cursor" else stream(process, args.provider)
        await asyncio.wait_for(run, timeout=args.timeout)
    finally:
        if process.returncode is None:
            process.stdin.close()
            try:
                await asyncio.wait_for(process.wait(), timeout=3)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
    return check(work)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provider", choices=["codex", "antigravity", "cursor"])
    parser.add_argument("--model", required=True, help="An ID offered to your signed-in CLI")
    parser.add_argument("--binary", help="Optional absolute executable path")
    parser.add_argument("--timeout", type=int, default=300, help="Episode timeout in seconds")
    sys.exit(asyncio.run(main(parser.parse_args())))
