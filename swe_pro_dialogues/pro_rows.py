"""Read the public task text from the pinned SWE-bench Pro V2 Python split."""

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from statistics import median


DATASET = "ScaleAI/SWE-bench_Pro"
REVISION = "2d52cb3df914a3fcf80c7f66738b3a88ae37fc50"
PARQUET_SHA256 = "1067f72c1f43bbc578276888625db3b836cebb535546c9eaf824c5d5dd104a7f"
PUBLIC_COLUMNS = (
    "instance_id", "repo", "base_commit", "repo_language", "version",
    "problem_statement", "requirements", "interface", "docker_image",
)
# The pinned Python split includes an unspaced dash, a prose preamble,
# indented continuations and a Markdown rule inside a multiline example.
BULLET = re.compile(r"^[-*+](?:[^\S\n]+|(?=[A-Za-z`]))")


def fingerprint(value):
    serialized = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def requirement_items(text):
    """Number top-level requirements in source order, retaining multiline text."""
    items, current = [], []
    for line in text.splitlines():
        marker = BULLET.match(line)
        if marker:
            if any(part.strip() for part in current):
                items.append("\n".join(current).strip())
            current = [line[marker.end():]]
        else:
            current.append(line)
    if any(part.strip() for part in current):
        items.append("\n".join(current).strip())
    if not items:
        raise ValueError("Empty requirements")
    return {f"r{i}": item for i, item in enumerate(items, 1)}


def load_python_rows(parquet):
    import pyarrow.parquet as pq

    path = Path(parquet)
    if hashlib.sha256(path.read_bytes()).hexdigest() != PARQUET_SHA256:
        raise ValueError("Expected the pinned default/test V2 Parquet file")
    rows = pq.read_table(path, columns=list(PUBLIC_COLUMNS),
                         filters=[("repo_language", "=", "python")]).to_pylist()
    by_id = {row["instance_id"]: row for row in rows}
    if len(by_id) != len(rows) or any(row["version"] != "2.0.0" for row in rows):
        raise ValueError("Unexpected source version or duplicate task ID")
    return by_id


def full_prompt(row):
    return (row["problem_statement"] + "\n\n## Requirements\n\n" + row["requirements"]
            + "\n\n## Interfaces\n\n" + row["interface"])


def inventory(rows):
    counts = [len(requirement_items(row["requirements"])) for row in rows.values()]
    return {"python_tasks": len(rows), "repositories": dict(Counter(r["repo"] for r in rows.values())),
            "median_requirement_items": median(counts),
            "at_least_three_items": sum(n >= 3 for n in counts),
            "at_least_four_items": sum(n >= 4 for n in counts)}
