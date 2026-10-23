"""Pieces file: one opening task plus follow-up instructions per instance (HARNESS.md 3.1)."""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


class Release(BaseModel):
    """When a piece is released in the `interrupt` condition. Ignored by `upfront` and `wait`."""

    model_config = ConfigDict(extra="forbid")

    after_step: int | None = None
    """Release after the agent's k-th model call."""
    after_first_edit: bool = False
    """Release once the working tree first differs from the base commit..."""
    plus_steps: int = 0
    """...plus this many steps."""

    @model_validator(mode="after")
    def _exactly_one_trigger(self):
        if (self.after_step is not None) == self.after_first_edit:
            raise ValueError("release needs exactly one of after_step or after_first_edit")
        if self.after_step is not None and self.after_step < 1:
            raise ValueError("after_step must be >= 1")
        if self.plus_steps < 0 or (self.plus_steps and not self.after_first_edit):
            raise ValueError("plus_steps must be >= 0 and only goes with after_first_edit")
        return self

    @property
    def label(self) -> str:
        if self.after_first_edit:
            return f"after_first_edit+{self.plus_steps}"
        return f"after_step={self.after_step}"


class Piece(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    text: str
    release: Release | None = None


class TaskPieces(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pieces: list[Piece]
    tags: dict[str, Any] = {}
    """Passed through untouched to the output (RQ3 grouping)."""

    @model_validator(mode="after")
    def _check(self):
        if not self.pieces:
            raise ValueError("pieces must contain at least the opening task (pieces[0])")
        ids = [p.id for p in self.pieces]
        if len(ids) != len(set(ids)):
            raise ValueError(f"piece ids must be unique, got {ids}")
        return self

    def check_for(self, condition: str) -> None:
        """`interrupt` needs a release rule on every piece after the first."""
        if condition == "interrupt":
            missing = [p.id for p in self.pieces[1:] if p.release is None]
            if missing:
                raise ValueError(f"interrupt condition needs a release rule on pieces {missing}")


def load_pieces(path: Path | str, *, condition: str = "") -> dict[str, TaskPieces]:
    """Load and validate a pieces file. Raises on any error so a bad file never starts a run."""
    raw = json.loads(Path(path).read_text())
    out = {instance_id: TaskPieces.model_validate(entry) for instance_id, entry in raw.items()}
    if condition:
        for task in out.values():
            task.check_for(condition)
    return out
