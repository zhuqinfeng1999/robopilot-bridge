# 🌉 RoboPilot Bridge

Connect a signed-in **Codex**, **Google Antigravity**, or **Cursor** client to a robotics harness through a small MCP tool surface. This Python 3.11+ starter ships a four-cell simulator with state, RGB observations, revision-checked actions, and an independently checkable goal.

[中文](README.md) · [Provider recipes](docs/providers.md) · [Robot adapters](docs/embodiments.md) · [Agent entry point](AGENTS.md)

1. Clone the repository and run `python -m unittest -v` for the offline loop.
2. Sign into one official CLI on your machine. Select a model currently available to that account.
3. Run `python run_client.py codex --model MODEL_ID`, substituting `antigravity` or `cursor` as needed.
4. Inspect the printed episode directory. The owner writes `events.jsonl`; `python pilot.py check runs/<episode>` checks the last simulator result.
5. For interactive setup, run `python pilot.py init PROVIDER runs/my-trial`, open that directory in the signed-in client, approve the local rail server and send the contents of `TASK.txt`.

The client handles account authentication. No hosted endpoint or API key is required by the simulator. Available models, usage quotas and sign-in methods depend on the installed CLI and your account. The reference workspace is for simulation. Hardware adapters must implement their own controller feedback, limits, cancellation and supervision.
