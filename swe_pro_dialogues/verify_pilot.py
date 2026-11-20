"""Check source identities, labels, the matched length contrast and message release offline."""

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys

from pilot import HERE, LITE, label_record, merge_additions, read
from pro_rows import DATASET, REVISION, fingerprint

sys.path.insert(0, str(LITE))
from verify_release import verify_delivery
from benchmark_data import load_candidates
from model_pilot import digest


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def verify(folder):
    primary = load_candidates(folder)
    manifest = read(folder / "manifest.json")
    require(manifest["files"]["length_comparison.jsonl"] == digest(folder / "length_comparison.jsonl"),
            "Length comparison differs from the manifest")
    comparisons = read_lines(folder / "length_comparison.jsonl")
    plans = {p["name"]: p for p in read(HERE / "plans.json")}
    reviews = read(HERE / "reviews.json")
    by_id = {r["group_id"]: r for r in primary}
    require(len(by_id) == len(primary) == len(plans), "Expected one primary per reviewed original")
    require(set(by_id) == {p["instance_id"] for p in plans.values()}, "Original IDs differ")
    index = read_lines(folder / "evaluation_sources.jsonl")
    require(len(index) == len(by_id) and {r["instance_id"] for r in index} == set(by_id), "Invalid grader index")
    for entry in index:
        name = by_id[entry["instance_id"]]["provenance"]["plan"]
        require(entry["grading_sha256"] == reviews[name]["grading_sha256"], "Grading reference differs")
    require({r["group_id"] for r in comparisons} ==
            {p["instance_id"] for p in plans.values() if "merge_additions_for_primary" in p}
            and len(comparisons) == len({r["group_id"] for r in comparisons}), "Unexpected comparison group")
    for record in primary + comparisons:
        plan = plans[record["provenance"]["plan"]]
        review = reviews[plan["name"]]
        require(record["source"]["dataset"] == DATASET and record["source"]["revision"] == REVISION
                and record["source"]["instance_id"] == record["group_id"] == plan["instance_id"],
                "Source identity differs")
        require(fingerprint(plan) == review["plan_sha256"] == record["provenance"]["plan_sha256"]
                and fingerprint(review["answer"]) == review["answer_sha256"] == record["provenance"]["answer_sha256"]
                and fingerprint(record["full_prompt"]) == review["full_prompt_sha256"], "Reviewed inputs differ")
        require(label_record(record) == record, "Trajectory label or counts differ")
        expected = deepcopy(review["answer"]["messages"])
        expected[-1]["content"] += "\n\n" + record["full_prompt"]
        if len(expected) != len(record["messages"]):
            i, j = plan["merge_additions_for_primary"]
            expected[i:j + 1] = [{"content": expected[i]["content"] + "\n\n" + expected[j]["content"]}]
        require(record["messages"] == [dict(m, id=f"U{i}") for i, m in enumerate(expected)],
                "Published messages differ from the approved wording")
        active = set()
        for stage in record["stage_annotations"]:
            require(set(stage["retired_ids"]) <= active, "Unknown retirement")
            active.difference_update(stage["retired_ids"])
            active.update(stage["added_ids"])
            require(active == set(stage["active_ids"]), "Stage state differs")
        require(active == set(record["final_requirement_ids"]) and not record["stage_annotations"][-1]["unresolved"],
                "Incomplete final stage")
        for mode in ("full", "wait", "interrupt"):
            verify_delivery(record, mode)
    for long in comparisons:
        short = by_id[long["group_id"]]
        merged = merge_additions(long, plans[long["provenance"]["plan"]]["merge_additions_for_primary"])
        for key in ("source", "evaluation", "trajectory_type", "final_requirement_ids", "full_prompt", "messages", "stage_annotations"):
            require(merged[key] == short[key], f"Matched length comparison differs on {key}")
    return {"originals": len(primary), "primary_lengths": dict(Counter(r["n_messages"] for r in primary)),
            "primary_categories": dict(Counter(r["trajectory_type"] for r in primary)),
            "same_original_four_message_comparisons": len(comparisons),
            "scripted_episodes": 3 * (len(primary) + len(comparisons))}


if __name__ == "__main__":
    print(json.dumps(verify(Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "pilot_v1"), indent=2))
