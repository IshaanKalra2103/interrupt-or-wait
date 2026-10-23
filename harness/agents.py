"""Agents for the three delivery conditions (HARNESS.md 2 and 4).

All three share one execute_actions (so submits are handled identically) and one snapshot per step.
They differ only in when pieces reach the model:
- UpfrontAgent: all pieces joined into the opening task.
- InterruptAgent: after the step where a piece's release trigger fires (or on an early submit).
- WaitAgent: each time the agent submits.
"""

import time

from jinja2 import StrictUndefined, Template

from minisweagent.agents.default import AgentConfig, DefaultAgent
from minisweagent.exceptions import InterruptAgentFlow, Submitted

from harness.pieces import Piece, TaskPieces
from harness.snapshots import Snapshotter

SUBMIT_MARKER = "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"


class DeliveryAgentConfig(AgentConfig):
    piece_template: str = "<user_update>\n{{piece}}\n</user_update>\n"
    """Wrapper around every added piece. Identical across conditions."""
    snapshots: bool = True
    """Take a code snapshot after every step (needs a git repo in the environment's cwd)."""


class DeliveryAgent(DefaultAgent):
    condition = ""

    def __init__(self, model, env, *, pieces: TaskPieces, config_class: type = DeliveryAgentConfig, **kwargs):
        super().__init__(model, env, config_class=config_class, **kwargs)
        pieces.check_for(self.condition)
        self.pieces = pieces
        self.next_piece = 0
        self.first_edit_step: int | None = None
        self.deliveries: list[dict] = []
        self.rounds: list[dict] = []
        self.snapshots: list[dict] = []
        self.snapshotter: Snapshotter | None = None

    def opening_pieces(self) -> list[Piece]:
        return self.pieces.pieces[:1]

    def run(self, task: str = "", **kwargs) -> dict:
        """The task is built from the opening pieces; `task` is ignored."""
        if self.config.snapshots:
            self.snapshotter = Snapshotter(self.env)
        opening = self.opening_pieces()
        self.next_piece = len(opening)
        self.deliveries = [self._delivery_record(p, "opening") for p in opening]
        try:
            return super().run("\n\n".join(p.text for p in opening), **kwargs)
        finally:
            for piece in self.pieces.pieces[self.next_piece :]:
                self.deliveries.append({"piece_id": piece.id, "status": "undelivered", "condition": self.condition})
            self.save(self.config.output_path)

    def step(self) -> list[dict]:
        return super().step() + self.after_step()

    def after_step(self) -> list[dict]:
        """Hook for step-triggered delivery. All tool messages of the step are in place by now."""
        return []

    def execute_actions(self, message: dict) -> list[dict]:
        """Like InteractiveAgent.execute_actions: try/finally keeps tool messages when Submitted fires."""
        outputs, submitted = [], None
        try:
            for action in message.get("extra", {}).get("actions", []):
                outputs.append(self.env.execute(action))
        except Submitted as e:
            submitted = e
            # The env raised before returning the submit command's output; restore it so the tool
            # message shows what the command printed instead of "action was not executed".
            outputs.append({"output": f"{SUBMIT_MARKER}\n{self._submission(e)}", "returncode": 0, "exception_info": ""})
        finally:
            result = self.add_messages(
                *self.model.format_observation_messages(message, outputs, self.get_template_vars())
            )
            self.take_snapshot()
        if submitted is not None:
            self.on_submit(submitted)
        return result

    def on_submit(self, e: Submitted) -> None:
        """Record the round. If pieces remain, deliver the next one and keep going; else end the run."""
        final = self.next_piece >= len(self.pieces.pieces)
        self.rounds.append(
            {"round": len(self.rounds) + 1, "step": self.n_calls, "final": final, "submission": self._submission(e)}
        )
        if final:
            raise e
        raise InterruptAgentFlow(self.deliver(trigger="on_submit", early_submit=self.condition != "wait"))

    def deliver(self, *, trigger: str, early_submit: bool = False) -> dict:
        piece = self.pieces.pieces[self.next_piece]
        self.next_piece += 1
        record = self._delivery_record(piece, trigger, early_submit=early_submit)
        self.deliveries.append(record)
        content = Template(self.config.piece_template, undefined=StrictUndefined).render(piece=piece.text)
        tags = {k: record[k] for k in ("piece_id", "condition", "trigger", "step", "early_submit", "t")}
        return self.model.format_message(role="user", content=content, extra={"interrupt_type": "InjectedInstruction", **tags})

    def _delivery_record(self, piece: Piece, trigger: str, *, early_submit: bool = False) -> dict:
        last = self.snapshots[-1] if self.snapshots else None
        return {
            "piece_id": piece.id,
            "status": "delivered",
            "condition": self.condition,
            "trigger": trigger,
            "step": self.n_calls,
            "early_submit": early_submit,
            "t": time.time(),
            "snapshot_step": last["step"] if last else None,
            "diffstat_at_delivery": last["diffstat"] if last else None,
        }

    @staticmethod
    def _submission(e: Submitted) -> str:
        return e.messages[0].get("extra", {}).get("submission", "")

    def take_snapshot(self) -> None:
        if self.snapshotter is None:
            return
        snap = self.snapshotter.take(self.n_calls)
        self.snapshots.append(snap)
        if self.first_edit_step is None and snap["diff"].strip():
            self.first_edit_step = self.n_calls

    def serialize(self, *extra_dicts) -> dict:
        harness = {
            "condition": self.condition,
            "base_sha": self.snapshotter.base_sha if self.snapshotter else "",
            "tags": self.pieces.tags,
            "pieces": [p.model_dump() for p in self.pieces.pieces],
            "first_edit_step": self.first_edit_step,
            "deliveries": self.deliveries,
            "rounds": self.rounds,
            "snapshot_seconds": round(sum(s["seconds"] for s in self.snapshots), 4),
            "snapshots": self.snapshots,
        }
        return super().serialize({"harness": harness}, *extra_dicts)


class UpfrontAgent(DeliveryAgent):
    condition = "upfront"

    def opening_pieces(self) -> list[Piece]:
        return self.pieces.pieces


class InterruptAgent(DeliveryAgent):
    condition = "interrupt"

    def after_step(self) -> list[dict]:
        """At most one piece per step, in order."""
        if self.next_piece >= len(self.pieces.pieces):
            return []
        release = self.pieces.pieces[self.next_piece].release
        if release.after_first_edit:
            fires = self.first_edit_step is not None and self.n_calls >= self.first_edit_step + release.plus_steps
        else:
            fires = self.n_calls >= release.after_step
        return self.add_messages(self.deliver(trigger=release.label)) if fires else []


class WaitAgent(DeliveryAgent):
    condition = "wait"


AGENTS = {"upfront": UpfrontAgent, "interrupt": InterruptAgent, "wait": WaitAgent}
