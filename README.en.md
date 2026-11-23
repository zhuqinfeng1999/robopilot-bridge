# 🌉 RoboPilot Bridge

Connect a signed-in **Codex**, **Google Antigravity**, or **Cursor** client to your robotics harness. [中文首页](README.md)

## Give this prompt to your AI agent

Copy the entire block into a coding agent that can run commands on your computer. It will use the subscription available in your official client. One model-driven episode uses that client’s quota.

```text
Set up RoboPilot Bridge on my computer and run one simulated pick-and-place episode using my signed-in subscription.
Repository: https://github.com/zhuqinfeng1999/robopilot-bridge

1. Reuse the current checkout if it is this repository. Otherwise clone it into a new subdirectory. Read AGENTS.md and docs/providers.md, then run python -m unittest -v from the repository root with Python 3.11+.
2. Check the official Codex, Antigravity and Cursor CLIs on this machine. Use my preferred client if specified. If exactly one is signed in, use it. If several are signed in, ask me to choose. Confirm an available model in that client. Let me handle any sign-in or approval in the official interface and keep credentials there.
3. Run run_client.py with the chosen client and its actual model ID. Connect the rail MCP tools and run one simulator episode. If tools need interactive approval, follow the documented interactive workflow for the same task. Use only the simulator for this setup.
4. Check the client’s terminal event and run python pilot.py check on the actual episode directory. Verify "episode_success": true, then report the client, model, run directory and exact command I can reuse. If blocked, name the failed step and its cause.
```

### What the bridge connects

| Signed-in client | How the harness sends the task | How the episode ends |
|---|---|---|
| 🟦 Codex | `codex exec --json` with a process-scoped MCP server | A successful turn and process exit |
| 🟪 Google Antigravity | `agy` with bidirectional stream-json and a project MCP config | A `result` event with status `SUCCESS` |
| 🟧 Cursor | `agent acp` with an MCP server attached to the ACP session | The prompt returns `end_turn` |

All three routes expose the same tools. The planner calls `observe` for an RGB image and state, calls `act` with the latest observation revision, and calls `finish` when it is done. The simulator checks whether the red puck was released on the green goal.

| Observe | Grasp | Release on goal |
|:---:|:---:|:---:|
| ![Blue gripper in cell one, red puck in cell two](docs/images/observe.png) | ![Gripper holding the puck in cell two](docs/images/grasp.png) | ![Red puck at rest on the green goal in cell four](docs/images/release.png) |

### Run it yourself

From a checkout with Python 3.11 or later, run the offline tests first. They use the standard library and require no login.

```sh
git clone https://github.com/zhuqinfeng1999/robopilot-bridge.git
cd robopilot-bridge
python -m unittest -v
```

Choose **one** of the following commands and replace `MODEL_ID` with a model available in your signed-in CLI.

```sh
python run_client.py codex --model MODEL_ID
python run_client.py antigravity --model MODEL_ID
python run_client.py cursor --model MODEL_ID
```

Copy the directory printed after `SIM workspace` and pass it to `python pilot.py check`. A completed task produces `"episode_success": true`. For interactive setup, run `python pilot.py init PROVIDER runs/my-trial`, open that directory in the chosen CLI, enable the local `rail` tools, and send the contents of `TASK.txt`.

### Take it to your robotics harness

Keep the planner session and tool interface when you replace the simulator. An arm can expose a placement skill, a humanoid can expose a reach skill while its controller maintains balance, and a dexterous hand can report fingertip contact after a grasp. Let the local executor validate each action, report its outcome, and handle stops. Validate a new adapter in replay and simulation before an attended hardware run. The repository includes offline simulator and protocol tests. Live subscription access depends on the installed client and account. [Agent instructions](AGENTS.md) · [Provider recipes (中文)](docs/providers.md) · [Hardware adapters (中文)](docs/embodiments.md) · [Validation scope (中文)](docs/validation.md)
