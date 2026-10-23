"""Acceptance tests 1-6 from HARNESS.md section 9, with a scripted model (no API key)."""

import json
import subprocess

import pytest
from pydantic import ValidationError

from minisweagent.environments.local import LocalEnvironment

from harness import toy
from harness.agents import AGENTS
from harness.checks import pairing_violations
from harness.pieces import TaskPieces, load_pieces
from harness.snapshots import Snapshotter


def pieces(release: dict | None = None) -> TaskPieces:
    return TaskPieces.model_validate(
        {
            "pieces": [
                {"id": "p0", "text": toy.PIECES.pieces[0].text},
                {"id": "p1", "text": toy.PIECES.pieces[1].text, "release": release or {"after_first_edit": True}},
            ]
        }
    )


def run(tmp_path, condition, script, task_pieces=toy.PIECES, **kwargs):
    repo = toy.make_repo(tmp_path / f"repo-{condition}")
    agent = AGENTS[condition](
        toy.scripted_model(script),
        LocalEnvironment(cwd=str(repo)),
        pieces=task_pieces,
        system_template=toy.SYSTEM,
        instance_template=toy.INSTANCE,
        cost_limit=0,
        output_path=tmp_path / f"{condition}.traj.json",
        **kwargs,
    )
    info = agent.run()
    return agent, info, repo


def injected(messages):
    return [i for i, m in enumerate(messages) if m.get("extra", {}).get("interrupt_type") == "InjectedInstruction"]


# 1. Message order per condition


def test_upfront_puts_all_pieces_in_the_task(tmp_path):
    agent, info, repo = run(tmp_path, "upfront", toy.SCRIPTS["upfront"])
    roles = [m["role"] for m in agent.messages]
    assert roles == ["system", "user"] + ["assistant", "tool"] * 4 + ["exit"]
    assert all(p.text in agent.messages[1]["content"] for p in toy.PIECES.pieces)
    assert injected(agent.messages) == []
    assert [d["status"] for d in agent.deliveries] == ["delivered", "delivered"]
    assert info["exit_status"] == "Submitted"
    assert toy.toy_checks(repo) == {"p0": True, "p1": True}


def test_interrupt_piece_lands_right_after_trigger_steps_tool_messages(tmp_path):
    agent, info, repo = run(tmp_path, "interrupt", toy.SCRIPTS["interrupt"])
    # 0 system, 1 task, 2-3 step 1 (cat), 4-5 step 2 (first edit) -> piece at 6
    assert injected(agent.messages) == [6]
    assert agent.messages[5]["role"] == "tool"
    extra = agent.messages[6]["extra"]
    assert (extra["piece_id"], extra["trigger"], extra["step"], extra["early_submit"]) == ("p1", "after_first_edit+0", 2, False)
    assert "<user_update>" in agent.messages[6]["content"]
    assert agent.first_edit_step == 2
    assert info["exit_status"] == "Submitted"
    assert toy.toy_checks(repo) == {"p0": True, "p1": True}


def test_wait_piece_lands_after_submit(tmp_path):
    agent, info, repo = run(tmp_path, "wait", toy.SCRIPTS["wait"])
    # steps 1-4 fill 2..9; step 4 is the submit, its tool message at 9 -> piece at 10
    assert injected(agent.messages) == [10]
    assert agent.messages[9]["role"] == "tool"
    assert "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT" in agent.messages[9]["content"]
    assert agent.messages[10]["extra"]["trigger"] == "on_submit"
    assert toy.toy_checks(repo) == {"p0": True, "p1": True}


# 2. No user message between a tool call and its reply


@pytest.mark.parametrize("condition", list(AGENTS))
def test_saved_trajectories_keep_tool_calls_paired(tmp_path, condition):
    agent, _, _ = run(tmp_path, condition, toy.SCRIPTS[condition])
    saved = json.loads(agent.config.output_path.read_text())
    assert pairing_violations(saved["messages"]) == []
    assert saved["harness"]["condition"] == condition


def test_pairing_checker_catches_a_user_message_inside_a_step():
    bad = [
        {"role": "assistant", "tool_calls": [{"id": "a"}]},
        {"role": "user", "content": "too early"},
        {"role": "tool", "tool_call_id": "a"},
    ]
    assert len(pairing_violations(bad)) == 2


# 3. Wait: two submissions -> two rounds, one final


def test_wait_records_each_round(tmp_path):
    agent, info, _ = run(tmp_path, "wait", toy.SCRIPTS["wait"])
    assert [(r["round"], r["step"], r["final"]) for r in agent.rounds] == [(1, 4, False), (2, 7, True)]
    assert "a + b" in agent.rounds[0]["submission"] and "c=0" not in agent.rounds[0]["submission"]
    assert "c=0" in agent.rounds[1]["submission"]
    assert info["exit_status"] == "Submitted" and info["submission"] == agent.rounds[1]["submission"]
    # the piece's delivery record carries the code state the change arrived on
    assert agent.deliveries[1]["diffstat_at_delivery"]["files"] == ["calc.py"]


# 4. Early submit in interrupt


def test_interrupt_early_submit_still_delivers_and_flags(tmp_path):
    script = [("Look.", "cat calc.py"), ("Fix.", toy.FIX_BUG), ("Submit.", toy.SUBMIT), ("Add c.", toy.FIX_BOTH), ("Submit.", toy.SUBMIT)]
    agent, info, repo = run(tmp_path, "interrupt", script, task_pieces=pieces({"after_step": 10}))
    p1 = agent.deliveries[1]
    assert (p1["status"], p1["trigger"], p1["step"], p1["early_submit"]) == ("delivered", "on_submit", 3, True)
    assert agent.messages[injected(agent.messages)[0]]["extra"]["early_submit"] is True
    assert len(agent.rounds) == 2 and info["exit_status"] == "Submitted"
    assert toy.toy_checks(repo)["p1"]


# 5. Snapshots catch new files without touching the agent's git state


def test_snapshots_include_new_files_and_leave_git_status_alone(tmp_path):
    script = [("Note.", "echo hi > notes.txt"), ("Fix.", toy.FIX_BUG), ("Submit.", toy.SUBMIT)]
    single = TaskPieces.model_validate({"pieces": [{"id": "p0", "text": "fix add"}]})
    agent, _, repo = run(tmp_path, "upfront", script, task_pieces=single)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
    assert agent.snapshotter.base_sha == head
    assert agent.snapshots[0]["diffstat"]["files"] == ["notes.txt"]
    assert sorted(agent.snapshots[-1]["diffstat"]["files"]) == ["calc.py", "notes.txt"]
    assert all(s["seconds"] >= 0 for s in agent.snapshots)
    status = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True).stdout
    assert "?? notes.txt" in status and "A  notes.txt" not in status
    assert " M calc.py" in status


def test_snapshot_sees_same_size_edit_right_after_commit(tmp_path):
    repo = toy.make_repo(tmp_path / "repo")
    snapshotter = Snapshotter(LocalEnvironment(cwd=str(repo)))
    (repo / "calc.py").write_text(toy.BUGGY.replace("a - b", "a + b"))  # same size, same second
    assert snapshotter.take(1)["diffstat"] == {"files": ["calc.py"], "added": 1, "removed": 1}


# 6. Step limit hit before a piece is due -> undelivered


def test_piece_not_yet_due_at_step_limit_is_logged_undelivered(tmp_path):
    script = [("Look.", "cat calc.py")] * 5
    agent, info, _ = run(tmp_path, "interrupt", script, task_pieces=pieces({"after_step": 10}), step_limit=3)
    assert info["exit_status"] == "LimitsExceeded"
    assert agent.deliveries[1] == {"piece_id": "p1", "status": "undelivered", "condition": "interrupt"}
    saved = json.loads(agent.config.output_path.read_text())
    assert saved["harness"]["deliveries"][1]["status"] == "undelivered"


# Pieces file validation (HARNESS.md 3.1)


def test_pieces_file_validation(tmp_path):
    good = {"x": {"pieces": [{"id": "p0", "text": "a"}, {"id": "p1", "text": "b", "release": {"after_step": 2}}]}}
    path = tmp_path / "pieces.json"
    path.write_text(json.dumps(good))
    assert load_pieces(path, condition="interrupt")["x"].pieces[1].release.label == "after_step=2"
    with pytest.raises(ValidationError):
        TaskPieces.model_validate({"pieces": [{"id": "p0", "text": "a"}, {"id": "p0", "text": "b"}]})
    with pytest.raises(ValidationError):
        TaskPieces.model_validate({"pieces": [{"id": "p0", "text": "a", "release": {"after_step": 1, "after_first_edit": True}}]})
    with pytest.raises(ValueError):
        TaskPieces.model_validate({"pieces": [{"id": "p0", "text": "a"}, {"id": "p1", "text": "b"}]}).check_for("interrupt")
