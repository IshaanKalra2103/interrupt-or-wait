"""Toy task (calc.py, one bug + one follow-up requirement) under all three conditions.

    uv run python -m harness.toy                                   # scripted model, no API key
    uv run python -m harness.toy --model ollama_chat/<tag>         # real local model via Ollama
    uv run python -m harness.toy --condition wait --model ollama_chat/<tag> --step-limit 20
"""

import os

os.environ.setdefault("MSWEA_SILENT_STARTUP", "1")

import argparse
import json
import re
import subprocess
import tempfile
import traceback
from pathlib import Path

from minisweagent.environments.local import LocalEnvironment
from minisweagent.models import get_model
from minisweagent.models.test_models import DeterministicToolcallModel, make_toolcall_output

from harness.agents import AGENTS
from harness.checks import pairing_violations
from harness.pieces import TaskPieces

BUGGY = "def add(a, b):\n    return a - b\n"
SUBMIT = "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT && git diff"

PIECES = TaskPieces.model_validate(
    {
        "pieces": [
            {"id": "p0", "text": "add(2, 3) in calc.py returns -1 but should return 5. Fix add()."},
            {
                "id": "p1",
                "text": "New requirement: add() must also accept an optional third argument c=0 and return a + b + c.",
                "release": {"after_first_edit": True, "plus_steps": 0},
            },
        ],
        "tags": {"task_type": "toy", "split_kind": "additive"},
    }
)

SYSTEM = "You are a helpful assistant that can interact with a computer shell to solve programming tasks."
INSTANCE = (
    "Task:\n{{task}}\n\n"
    "Use the bash tool to run shell commands in the current directory, which contains calc.py. "
    "Each command runs in a fresh shell.\n"
    "The user may send new or changed requirements while you work or after you submit. "
    "If they do, address them and submit again.\n"
    "When you are done, submit by running exactly this command on its own:\n" + SUBMIT + "\n"
)

FIX_BUG = "printf 'def add(a, b):\\n    return a + b\\n' > calc.py"
FIX_BOTH = "printf 'def add(a, b, c=0):\\n    return a + b + c\\n' > calc.py"
CHECK_BUG = "python3 -c 'from calc import add; print(add(2, 3))'"
CHECK_BOTH = "python3 -c 'from calc import add; print(add(2, 3), add(1, 2, 3))'"

SCRIPTS = {
    "upfront": [("Look first.", "cat calc.py"), ("Fix both.", FIX_BOTH), ("Check.", CHECK_BOTH), ("Submit.", SUBMIT)],
    "interrupt": [
        ("Look first.", "cat calc.py"),
        ("Fix the bug.", FIX_BUG),
        ("New requirement: add c.", FIX_BOTH),  # p1 arrives after step 2 (first edit)
        ("Check.", CHECK_BOTH),
        ("Submit.", SUBMIT),
    ],
    "wait": [
        ("Look first.", "cat calc.py"),
        ("Fix the bug.", FIX_BUG),
        ("Check.", CHECK_BUG),
        ("Submit.", SUBMIT),  # p1 arrives here
        ("New requirement: add c.", FIX_BOTH),
        ("Check.", CHECK_BOTH),
        ("Submit again.", SUBMIT),
    ],
}


def make_repo(path: Path | None = None) -> Path:
    repo = Path(path or tempfile.mkdtemp(prefix="harness-toy-"))
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "calc.py").write_text(BUGGY)
    (repo / ".gitignore").write_text("__pycache__/\n")  # like real repos; snapshots respect .gitignore
    git =["git", "-c", "user.name=harness", "-c", "user.email=harness@example.com"]
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run([*git, "commit", "-qm", "base"], cwd=repo, check=True)
    return repo


def scripted_model(script: list[tuple[str, str]]) -> DeterministicToolcallModel:
    outputs = []
    for i, (thought, cmd) in enumerate(script, start=1):
        call_id = f"call_{i}"
        tool_call = {"id": call_id, "type": "function", "function": {"name": "bash", "arguments": json.dumps({"command": cmd})}}
        outputs.append(make_toolcall_output(thought, [tool_call], [{"command": cmd, "tool_call_id": call_id}]))
    return DeterministicToolcallModel(outputs=outputs, cost_per_call=0.0)


def real_model(model_name: str, temperature: float, num_ctx: int):
    # num_ctx: Ollama serves a 4096-token context by default, which the prompt plus tool output overflows.
    model_kwargs = {"temperature": temperature, "drop_params": True, "num_ctx": num_ctx}
    config = {"model_kwargs": model_kwargs, "cost_tracking": "ignore_errors"}
    return get_model(model_name, config)


def toy_checks(repo: Path) -> dict[str, bool]:
    """Did the final calc.py meet each requirement?"""
    probes = {"p0": "assert add(2, 3) == 5", "p1": "assert add(1, 2, 3) == 6 and add(2, 3) == 5"}
    result = {}
    for piece_id, probe in probes.items():
        proc = subprocess.run(["python3", "-c", f"from calc import add; {probe}"], cwd=repo, capture_output=True)
        result[piece_id] = proc.returncode == 0
    return result


def run_condition(
    condition: str, model_name: str, *, step_limit: int, out_dir: Path, temperature: float = 0.0, num_ctx: int = 12288
):
    repo = make_repo()
    model = scripted_model(SCRIPTS[condition]) if model_name == "scripted" else real_model(model_name, temperature, num_ctx)
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", model_name)
    agent = AGENTS[condition](
        model,
        LocalEnvironment(cwd=str(repo), timeout=30),
        pieces=PIECES,
        system_template=SYSTEM,
        instance_template=INSTANCE,
        step_limit=step_limit,
        cost_limit=0,
        output_path=out_dir / condition / f"{slug}.traj.json",
    )
    info = agent.run()
    return agent, info, repo


def short(text, width: int = 80) -> str:
    if isinstance(text, list):  # multimodal content blocks
        text = " ".join(block.get("text", "") for block in text if isinstance(block, dict))
    text = (text or "").replace("\n", " ⏎ ")
    return text if len(text) <= width else text[: width - 1] + "…"


def print_run(agent, info: dict, repo: Path) -> None:
    print(f"\n{'#':>3}  {'role':9} content")
    for i, msg in enumerate(agent.messages):
        role = msg.get("role", "?")
        mark = "★" if msg.get("extra", {}).get("interrupt_type") else " "
        calls = ", ".join(json.loads(tc["function"]["arguments"]).get("command", "") for tc in msg.get("tool_calls") or [])
        body = short(msg.get("content"), 70) + (f"  → [{short(calls, 60)}]" if calls else "")
        print(f"{i:>3}{mark} {role:9} {body}")
    for d in agent.deliveries:
        if d["status"] == "delivered":
            print(f"  piece {d['piece_id']}: {d['trigger']} at step {d['step']}" + (" (early submit)" if d["early_submit"] else ""))
        else:
            print(f"  piece {d['piece_id']}: UNDELIVERED")
    for r in agent.rounds:
        print(f"  round {r['round']}: submitted at step {r['step']}" + (" (final)" if r["final"] else ""))
    last = agent.snapshots[-1]["diffstat"] if agent.snapshots else {}
    print(f"  exit: {info.get('exit_status')}  steps: {agent.n_calls}  final diff: {last}")
    print(f"  requirement checks on final calc.py: {toy_checks(repo)}")
    if problems := pairing_violations(agent.messages):
        print(f"  PAIRING VIOLATIONS: {problems}")
    print(f"  trajectory: {agent.config.output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--condition", choices=["all", *AGENTS], default="all")
    parser.add_argument("--model", default="scripted", help="'scripted' or a litellm model name, e.g. ollama_chat/<tag>")
    parser.add_argument("--step-limit", type=int, default=30)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--num-ctx", type=int, default=12288, help="context window for Ollama models")
    parser.add_argument("--out", type=Path, default=Path("runs/toy"))
    args = parser.parse_args()

    for condition in AGENTS if args.condition == "all" else [args.condition]:
        print(f"\n===== {condition} · {args.model} =====")
        try:
            agent, info, repo = run_condition(
                condition, args.model, step_limit=args.step_limit, out_dir=args.out, temperature=args.temperature,
                num_ctx=args.num_ctx,
            )
        except Exception:
            traceback.print_exc()
            continue
        print_run(agent, info, repo)


if __name__ == "__main__":
    main()
