"""Small, model-independent delivery loop. Future messages stay in this controller.

One action is one completed shell call, a submission, or a clarification question.
The model sees the accumulated public transcript, never this controller/record.
"""

from copy import deepcopy
from datetime import datetime, timezone
import time


def timestamp():
    return datetime.now(timezone.utc).isoformat()


class DecisionBudgetExceeded(Exception):
    """A local limit stopped a decision before another model invocation."""


def validate_action(action):
    if not isinstance(action, dict) or set(action) != {"action", "command", "text"}:
        raise ValueError("Expected action, command and text only")
    if action["action"] not in ("shell", "submit", "ask"):
        raise ValueError("Unknown action")
    if not all(isinstance(action[k], str) for k in ("command", "text")):
        raise ValueError("Action fields must be strings")
    if (action["action"] == "shell") != bool(action["command"].strip()):
        raise ValueError("Only shell actions have a nonempty command")
    if action["action"] != "shell" and not action["text"].strip():
        raise ValueError("Submission/question needs text")
    return action


class Delivery:
    def __init__(self, record, condition="wait", interrupt_after=2):
        messages = record["messages"]
        if len(messages) not in (2, 3, 4) or any(m["id"] != "U" + str(i)
                                             for i, m in enumerate(messages)):
            raise ValueError("Expected two to four consecutive messages starting at U0")
        if condition not in ("wait", "interrupt", "full"):
            raise ValueError("Unknown condition")
        if type(interrupt_after) is not int or interrupt_after < 1:
            raise ValueError("Interruption must follow a completed tool action")
        self._messages = deepcopy(messages)
        self.condition = condition
        self.interrupt_after = interrupt_after
        self.stage = 0
        self.tools = self.tools_since_update = 0
        self.history, self.events = [], []
        self.status = "running"
        self.started = time.monotonic()
        if condition == "full":
            self.stage = len(messages) - 1
            self._release(record["full_prompt"], "full_upfront")
        else:
            self._release(messages[0]["content"], "initial")

    def _release(self, content, reason):
        self.history.append({"role": "user", "content": content})
        self.events.append({"event": "delivery", "stage": "U" + str(self.stage),
                            "reason": reason, "after_tools": self.tools,
                            "timestamp": timestamp()})
        self.tools_since_update = 0

    def visible_history(self):
        # A copy prevents adapters from modifying the controller transcript.
        return deepcopy(self.history)

    def accept(self, action, observation=None, snapshot=None, scripted_answer_reviewed=False):
        if self.status != "running":
            raise ValueError("Episode has ended")
        validate_action(action)
        if (action["action"] == "shell") != (observation is not None):
            raise ValueError("Exactly shell actions require a completed tool result")
        self.history.append({"role": "assistant", "content": deepcopy(action)})
        kind = action["action"]
        if kind == "shell":
            self.tools += 1
            self.tools_since_update += 1
            self.history.append({"role": "tool", "content": deepcopy(observation)})
        self.events.append({"event": kind, "stage": "U" + str(self.stage),
                            "after_tools": self.tools, "snapshot": snapshot,
                            "timestamp": timestamp()})
        pending = self.stage < len(self._messages) - 1
        if kind == "ask" and (not pending or not scripted_answer_reviewed):
            # Semantic alignment of a free-form question is not guessed.
            self.status = "needs_scripted_answer_review"
            return
        reason = None
        if kind in ("submit", "ask"):
            if pending:
                reason = ("question_reviewed" if kind == "ask" else "turn_end")
                if self.condition == "interrupt":
                    reason += "_before_scheduled_interrupt"
            else:
                self.status = "completed"
        elif pending and self.condition == "interrupt" and self.tools_since_update >= self.interrupt_after:
            reason = "tool_boundary"
        if reason:
            self.stage += 1
            self._release(self._messages[self.stage]["content"], reason)


def run_episode(controller, model, workspace, max_calls=16, max_seconds=1200):
    """Adapters: model(history, call_no)->action; workspace.execute/snapshot.

    No evaluator input/output enters this loop. Budgets cover the whole episode.
    Snapshots are captured after every action and before any next update.
    """
    calls = 0
    try:
        while controller.status == "running":
            if calls >= max_calls or time.monotonic() - controller.started >= max_seconds:
                controller.status = "budget_exhausted"
                break
            calls += 1
            action = validate_action(model(controller.visible_history(), calls))
            result = workspace.execute(action["command"]) if action["action"] == "shell" else None
            snapshot = workspace.snapshot(calls)
            controller.accept(action, result, snapshot)
    except DecisionBudgetExceeded as exc:
        controller.status = "budget_exhausted"
        controller.events.append({"event": "budget_stop", "detail": str(exc)})
    except Exception as exc:
        controller.status = "execution_error"
        controller.events.append({"event": "error", "type": type(exc).__name__, "detail": str(exc)})
    return {"status": controller.status, "model_calls": calls, "tool_calls": controller.tools,
            "released_stages": [e["stage"] for e in controller.events if e["event"] == "delivery"],
            "elapsed_seconds": round(time.monotonic() - controller.started, 3),
            "history": controller.visible_history(), "events": deepcopy(controller.events)}
