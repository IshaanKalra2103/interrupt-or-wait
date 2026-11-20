"""Derive English whole-trajectory labels from reviewed update annotations."""

import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import shutil

FAMILIES = {"addition": "cumulative", "clarification": "clarification",
            "revision": "revision", "retraction": "revision"}
TYPES = ("cumulative", "clarification", "revision", "mixed")
VERSION = "trajectory_v1"


def classify(update_types):
    if not isinstance(update_types, list) or not update_types:
        raise ValueError("Expected a nonempty ordered list of update types")
    if any(not isinstance(t, str) or t not in FAMILIES for t in update_types):
        raise ValueError("Unknown update type; mixed is derived, not a primitive operation")
    families = {FAMILIES[t] for t in update_types}
    return next(iter(families)) if len(families) == 1 else "mixed"


def label_record(record):
    messages = record["messages"]
    n = len(messages)
    if n not in (2, 3, 4) or [m["id"] for m in messages] != ["U" + str(i) for i in range(n)]:
        raise ValueError("Expected two to four consecutive messages starting at U0")
    updates = record.get("update_types")
    if updates is None:
        if n != 2:
            raise ValueError("Multi-update records need the ordered update_types")
        updates = [record["update_type"]]
    if not isinstance(updates, list) or len(updates) != n - 1:
        raise ValueError("Update count differs from message count")
    kind = classify(updates)
    for key, expected in (("n_messages", n), ("n_updates", n - 1), ("trajectory_type", kind)):
        if key in record and record[key] != expected:
            raise ValueError("Conflicting " + key)
    legacy_kind = updates[0] if len(set(updates)) == 1 else "mixed"
    if "update_type" in record and record["update_type"] != legacy_kind:
        raise ValueError("Legacy update_type disagrees with ordered updates")
    stages = record.get("stage_annotations", [])
    if stages:
        if [s["id"] for s in stages] != [m["id"] for m in messages]:
            raise ValueError("Stage annotations do not match messages")
        for stage, update in zip(stages[1:], updates):
            if "type" in stage and stage["type"] != update:
                raise ValueError("Stage operation disagrees with update_types")
    result = deepcopy(record)
    result.update(trajectory_type=kind, update_types=list(updates), n_messages=n, n_updates=n - 1,
                  classification={"version": VERSION, "method": "derived_from_update_annotations"})
    return result


def distribution(records):
    counts = Counter(r["trajectory_type"] for r in records)
    return {kind: counts[kind] for kind in TYPES}


def export_labeled(source, output):
    from benchmark_data import load_candidates, write_jsonl
    from model_pilot import digest, read_json, save
    source, output = Path(source).resolve(), Path(output).resolve()
    records = [label_record(r) for r in load_candidates(source)]
    manifest = deepcopy(read_json(source / "manifest.json"))
    output.mkdir(parents=True, exist_ok=False)
    write_jsonl(output / "candidates.jsonl", records)
    shutil.copyfile(source / "evaluation_sources.jsonl", output / "evaluation_sources.jsonl")
    manifest.update(classification_version=VERSION, trajectory_type_distribution=distribution(records),
                    parent_manifest_sha256=digest(source / "manifest.json"),
                    classification_scope="Metadata only; wording, source GT and validation status preserved")
    manifest["files"] = {name: digest(output / name) for name in ("candidates.jsonl", "evaluation_sources.jsonl")}
    save(output / "manifest.json", manifest)
    lines = ["# Classified development examples", "", "Labels do not upgrade validation status.", ""]
    for record in records:
        lines += ["## " + record["scenario_id"], "",
                  "Trajectory: `" + record["trajectory_type"] + "`; updates: `" +
                  " -> ".join(record["update_types"]) + "`.", ""]
        for message in record["messages"]:
            lines += ["**" + message["id"] + "**", "", message["content"], ""]
    (output / "examples.md").write_text("\n".join(lines), encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = export_labeled(args.input, args.output)
    print(json.dumps({k: result[k] for k in ("candidate_count", "original_task_count", "trajectory_type_distribution")}))


if __name__ == "__main__":
    main()
