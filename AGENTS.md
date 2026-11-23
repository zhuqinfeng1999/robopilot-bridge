# Agent handoff

This repository teaches a robotics harness to use models available to a signed-in **official client**. Keep one planner conversation per episode and preserve its ID for genuine continuations.

1. Read `README.md` and `docs/providers.md`. Run `python -m unittest -v` with Python 3.11+. A synthetic image and a completed simulated episode establish the local baseline.
2. Identify the chosen CLI, local binary version, account login status and selectable model. Let the operator complete the provider's interactive login when required. Keep session tokens, profiles and cookies inside the official client.
3. Use `run_client.py PROVIDER --model MODEL_ID` in a dedicated development account/profile whose enabled tools you have inspected. For an approval prompt, use `pilot.py init` and the interactive recipe. Only the rail server needs to be approved for this demo.
4. Verify a provider terminal event and owner `finish` result. Inspect the final state, action count and the requested/reported model. A CLI exit code alone is insufficient. Record unavailable metadata as unknown.
5. In a research harness, keep the task, selected public memory, observations and tool schemas visible to the planner. Keep human judgments, private scene conditions, secrets and reviewer policies outside its workspace. Give the baseline and reviewed variants separate model sessions and memory.
6. For a new platform, start with observation replay, then simulation, then a separately authorized attended hardware test. Use the platform's existing executor for feedback, motion limits, stale-state checks, stop handling and idempotency. See `docs/embodiments.md`.
7. Report precisely which of offline protocol, subscribed model inference and physical execution were actually verified. Never assign a physical outcome based on model prose.

Generated workspaces live under `runs/`. Never publish generated folders or a user's CLI configuration. The starter has no hardware control endpoint.
