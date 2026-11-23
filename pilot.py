"""Prepare a fresh, local subscription-client workspace for one simulated episode."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
TASK = ("Use the rail MCP tools. Move the red puck onto the green goal and release it. "
        "Observe first. Supply the current revision on every action. Call finish to check the result.")


def workspace(provider, directory):
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    server = {"command": sys.executable, "args": [str(ROOT / "sim_server.py"), "--audit", str(directory / "events.jsonl")]}
    if provider == "codex":
        config = directory / ".codex" / "config.toml"
        body = "[mcp_servers.rail]\ncommand = " + json.dumps(server["command"], ensure_ascii=False) + "\nargs = " + json.dumps(server["args"], ensure_ascii=False) + "\n"
    else:
        config = directory / (".cursor/mcp.json" if provider == "cursor" else ".agents/mcp_config.json")
        body = json.dumps({"mcpServers": {"rail": server}}, indent=2)
    config.parent.mkdir(parents=True)
    config.write_text(body, encoding="utf-8")
    (directory / "TASK.txt").write_text(TASK + "\n", encoding="utf-8")
    return config


def check(path):
    records = [json.loads(line) for line in (path / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    success = bool(records and records[-1]["tool"] == "finish" and records[-1]["state"].get("success") is True)
    print(json.dumps({"episode_success": success, "tool_calls": len(records),
                      "actions": sum(row["tool"] == "act" for row in records)}))
    return 0 if success else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    setup = subs.add_parser("init")
    setup.add_argument("provider", choices=["codex", "antigravity", "cursor"])
    setup.add_argument("directory", type=Path)
    verify = subs.add_parser("check")
    verify.add_argument("directory", type=Path)
    args = parser.parse_args()
    if args.command == "init":
        print(workspace(args.provider, args.directory))
        print(TASK)
    else:
        try:
            sys.exit(check(args.directory))
        except (OSError, ValueError, KeyError) as exc:
            sys.exit("No valid episode receipt: " + str(exc))
