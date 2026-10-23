"""Per-step code snapshots: full diff against the base commit, including files the agent created (HARNESS.md 5)."""

import time

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

# A throwaway index (inside .git, so concurrent runs on one machine don't collide) picks up new files
# without touching the agent's own index or `git status`. It is rebuilt from the base tree each time
# instead of copied from the agent's index: a copied stat cache misses same-size edits made within the
# same second (e.g. `a - b` -> `a + b`), so every file is re-hashed. Slower on big repos, never wrong.
SNAPSHOT_COMMAND = (
    'idx="$(git rev-parse --git-dir)/harness_snapshot_index" && rm -f "$idx" '
    '&& GIT_INDEX_FILE="$idx" git read-tree {base} '
    '&& GIT_INDEX_FILE="$idx" git add -A '
    '&& GIT_INDEX_FILE="$idx" git diff --cached --no-color {base}'
)


def diffstat(diff: str) -> dict:
    files, added, removed = [], 0, 0
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            files.append(line.split(" b/", 1)[-1])
        elif line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    return {"files": files, "added": added, "removed": removed}


class Snapshotter:
    """Runs git through the agent's environment. Output goes to the trajectory only; the model never sees it."""

    def __init__(self, env):
        self.env = env
        out = env.execute({"command": "git rev-parse HEAD"})
        self.base_sha = out["output"].strip() if out["returncode"] == 0 else EMPTY_TREE

    def take(self, step: int) -> dict:
        start = time.perf_counter()
        out = self.env.execute({"command": SNAPSHOT_COMMAND.replace("{base}", self.base_sha)})
        diff = out["output"] if out["returncode"] == 0 else ""
        return {
            "step": step,
            "t": time.time(),
            "seconds": round(time.perf_counter() - start, 4),
            "returncode": out["returncode"],
            "diffstat": diffstat(diff),
            "diff": diff,
        }
