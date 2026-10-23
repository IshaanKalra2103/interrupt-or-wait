# Interrupt or Wait?

Code for our CMSC723 (Fall 2026, UMD) final project, *Interrupt or Wait? A Systematic Study of Interruption in Coding Agents*. The project proposal is in [`proposal.pdf`](proposal.pdf).

It compares three ways of giving a coding agent instructions that arrive over time:
- **Upfront:** everything at the start.
- **Interrupt:** mid-run, right after a tool call.
- **Wait:** after the agent says it's done.

The harness runs SWE-bench Lite tasks on [mini-SWE-agent](https://github.com/SWE-agent/mini-swe-agent) and records a code snapshot after every step.

**The code is on the [`ishaank/harness`](https://github.com/IshaanKalra2103/interrupt-or-wait/tree/ishaank/harness) branch.** For now, `main` only has this README.

```bash
git clone -b ishaank/harness https://github.com/IshaanKalra2103/interrupt-or-wait
cd interrupt-or-wait
uv sync
uv run pytest                  # tests with a scripted model, no API key needed
uv run python -m harness.toy   # toy task under all three conditions
```
