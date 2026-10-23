"""Trajectory checks."""


def pairing_violations(messages: list[dict]) -> list[str]:
    """Every tool call must be answered by its tool message before any other message (HARNESS.md 4.1)."""
    problems, open_ids = [], []
    for i, msg in enumerate(messages):
        role = msg.get("role")
        if role == "tool":
            if msg.get("tool_call_id") in open_ids:
                open_ids.remove(msg["tool_call_id"])
            else:
                problems.append(f"message {i}: tool reply {msg.get('tool_call_id')!r} has no open tool call")
            continue
        if open_ids:
            problems.append(f"message {i} ({role}) arrives before tool calls {open_ids} were answered")
            open_ids = []
        if role == "assistant":
            open_ids = [tc["id"] for tc in msg.get("tool_calls") or []]
    if open_ids:
        problems.append(f"tool calls {open_ids} were never answered")
    return problems
