"""Construct and replay the author-side SWE-bench Pro V2 development pilot."""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile

from pro_rows import DATASET, PARQUET_SHA256, REVISION, fingerprint, full_prompt, inventory, load_python_rows, requirement_items


HERE = Path(__file__).resolve().parent
LITE = HERE.parent / "swe_lite_dialogues"
CODE = LITE / "split_pilot"
sys.path.insert(0, str(CODE))
from benchmark_data import write_jsonl
from model_pilot import digest, save
from trajectory_labels import label_record


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def prepare_stages(row, plan):
    """Bind each original bullet exactly once and replay changes to author state."""
    items = requirement_items(row["requirements"])
    stages, wording_stages = [], []
    introduced, active, pending = set(), set(), set()
    for i, spec in enumerate(plan["stages"]):
        sid, op = f"U{i}", spec["type"]
        public = [f"r{j}" for j in spec["bullets"]]
        temporary, opened = spec.get("temporary", {}), spec.get("open", {})
        retired, resolved = set(spec.get("retire", [])), set(spec.get("resolve", []))
        additions = public + list(temporary)
        if (not set(public) <= items.keys() or any(not k.startswith("t") for k in temporary)
                or len(set(additions)) != len(additions) or introduced.intersection(additions)):
            raise ValueError(f"{sid}: invalid, duplicated or already introduced requirement")
        if (not retired <= active or retired & items.keys() or not resolved <= pending
                or opened.keys() & pending or any(not k.startswith("q") for k in opened)):
            raise ValueError(f"{sid}: invalid retirement or change to an open question")
        if i == 0:
            if op != "initial" or not (additions or opened):
                raise ValueError("U0 needs an actionable request or open question")
        elif (op not in {"addition", "clarification", "revision", "retraction"}
              or (op == "clarification") != bool(resolved)
              or (op in {"revision", "retraction"}) != bool(retired)
              or (op != "retraction" and not additions)):
            raise ValueError(f"{sid}: annotated changes do not support the update type")
        introduced.update(additions)
        active = (active - retired).union(additions)
        pending = (pending - resolved).union(opened)
        stages.append({"id": sid, "type": op, "added_ids": additions, "retired_ids": sorted(retired),
                       "active_ids": sorted(active), "unresolved": sorted(pending),
                       "resolved_dimensions": sorted(resolved)})
        wording_stages.append({"id": sid, "operation": op, "focus": spec["focus"],
                               "new_source_requirements": [items[k] for k in public],
                               "temporary_requirements": temporary, "open_questions": opened,
                               "retire": sorted(retired), "resolve": sorted(resolved)})
    if active != items.keys() or pending:
        raise ValueError("The final requirements must equal the source with no open questions")
    if not 2 <= len(stages) <= 4:
        raise ValueError("Expected two to four stages")
    return stages, wording_stages


def wording_request(row, plan):
    _, stages = prepare_stages(row, plan)
    return {"repo": row["repo"], "problem_statement": row["problem_statement"],
            "interface": row["interface"], "stages": stages}


def wording_schema():
    schema = read(CODE / "phrasing_schema_v6.json")
    messages = schema["properties"]["messages"]
    messages["maxItems"] = 4
    messages["items"]["properties"]["id"]["enum"].append("U3")
    return schema


def draft(rows, plans, runs, live):
    from planned_generation import call_json

    config = dict(read(CODE / "codex_config.json"), model="gpt-6.1-sol", reasoning_effort="medium")
    prompt = (HERE / "wording_prompt.txt").read_text()
    schema = wording_schema()
    for plan in plans:
        source = wording_request(rows[plan["instance_id"]], plan)
        name = plan["name"]
        if not live:
            print(name, len(source["stages"]), fingerprint(source))
            continue
        if runs is None:
            raise ValueError("--live requires an author-side --runs directory")
        runs.mkdir(parents=True, exist_ok=True)
        case = runs / name
        if case.exists():
            expected = {"input": source, "developer_instructions": prompt, "schema": schema, "config": config}
            if read(case / "request.json") != expected:
                raise ValueError(f"{name}: existing request differs")
            print(f"{name}: existing attempt, skipped", flush=True)
            continue
        answer = call_json(source, prompt, schema, case, config=config)
        print(name, answer["decision"], flush=True)


def candidate(row, plan, review):
    stages, _ = prepare_stages(row, plan)
    answer = review["answer"]
    if (review["verdict"] != "accept_for_development" or answer["decision"] != "propose_split"
            or fingerprint(row) != review["public_row_sha256"]
            or fingerprint(plan) != review["plan_sha256"]
            or fingerprint(wording_request(row, plan)) != review["wording_input_sha256"]
            or fingerprint(answer) != review["answer_sha256"]
            or fingerprint((HERE / "wording_prompt.txt").read_text()) != review["prompt_sha256"]
            or fingerprint(wording_schema()) != review["schema_sha256"]):
        raise ValueError(f"{plan['name']}: unreviewed or changed source, plan or wording")
    messages = deepcopy(answer["messages"])
    if [m["id"] for m in messages] != [s["id"] for s in stages] or not all(m["content"].strip() for m in messages):
        raise ValueError("Wording stage IDs must match the plan")
    final_ids = list(requirement_items(row["requirements"]))
    interface_stage = review["interface_stage"]
    if row["interface"].strip() == "No new interfaces are introduced.":
        if interface_stage is not None:
            raise ValueError("No new public interface in this task")
    else:
        if type(interface_stage) is not int or not 0 <= interface_stage < len(stages):
            raise ValueError("Substantive interface needs a reviewed release stage")
        stages[interface_stage]["added_ids"].append("interface")
        for stage in stages[interface_stage:]:
            stage["active_ids"].append("interface")
        final_ids.append("interface")
    endpoint = full_prompt(row)
    messages[-1]["content"] += "\n\n" + endpoint
    record = {"schema_version": "pro-pilot-v1", "visibility": "author_controller_only", "split": "development",
              "scenario_id": "pro-v2." + plan["name"], "group_id": row["instance_id"],
              "source": {"dataset": DATASET, "config": "default", "split": "test", "revision": REVISION,
                         "instance_id": row["instance_id"], "repo": row["repo"], "base_commit": row["base_commit"]},
              "messages": messages, "stage_annotations": stages, "full_prompt": endpoint,
              "final_requirement_ids": final_ids,
              "evaluation": {"grader": "SWE-bench Pro V2", "original_instance_id": row["instance_id"],
                             "docker_image": row["docker_image"], "full_environment_validated": False},
              "validation": {"status": "offline_development_review", "agent_runs": 0},
              "provenance": {"plan": plan["name"], "plan_sha256": review["plan_sha256"],
                             "requested_model": review["requested_model"], "reasoning_effort": review["reasoning_effort"],
                             "answer_sha256": review["answer_sha256"], "public_row_sha256": fingerprint(row),
                             "construction": "author_grouped_official_bullets_and_model_wording"}}
    return record


def label(record):
    updates = [s["type"] for s in record["stage_annotations"][1:]]
    return label_record(dict(record, update_types=updates,
                             update_type=updates[0] if len(set(updates)) == 1 else "mixed"))


def merge_additions(record, positions):
    """Make the matched short version by issuing adjacent additions together."""
    first, second = positions
    stages, messages = record["stage_annotations"], record["messages"]
    if not (0 < first < second < len(stages) and second == first + 1):
        raise ValueError("Expected adjacent updates")
    a, b = stages[first:second + 1]
    if any(s["type"] != "addition" or s["retired_ids"] or s["resolved_dimensions"] for s in (a, b)):
        raise ValueError("Only compatible additions can be combined")
    result = deepcopy(record)
    result["stage_annotations"][first:second + 1] = [dict(b, added_ids=a["added_ids"] + b["added_ids"])]
    result["messages"][first:second + 1] = [{"content": messages[first]["content"] + "\n\n" + messages[second]["content"]}]
    for i, (stage, message) in enumerate(zip(result["stage_annotations"], result["messages"])):
        stage["id"] = message["id"] = f"U{i}"
    return result


def build(rows, plans, output, parquet):
    import pyarrow.parquet as pq

    reviews = read(HERE / "reviews.json")
    if len({p["instance_id"] for p in plans}) != len(plans) or set(reviews) != {p["name"] for p in plans}:
        raise ValueError("Expected one reviewed plan per original")
    scoring_columns = ["instance_id", "fail_to_pass", "pass_to_pass", "patch", "test_patch"]
    grading = pq.read_table(parquet, columns=scoring_columns,
                            filters=[("instance_id", "in", [p["instance_id"] for p in plans])])
    grading = {r["instance_id"]: r for r in grading.to_pylist()}
    primary, length_study, evaluator_index = [], [], []
    for plan in plans:
        iid = plan["instance_id"]
        review = reviews[plan["name"]]
        reference = grading[iid]
        if fingerprint(reference) != review["grading_sha256"]:
            raise ValueError("Original grading fields changed")
        targets = set(json.loads(reference["fail_to_pass"]))
        regressions = set(json.loads(reference["pass_to_pass"]))
        record = candidate(rows[iid], plan, review)
        mapped, covered = set(), set()
        for link in review["test_mapping"]:
            named = set(link["tests"])
            if not named or not named <= targets | regressions:
                raise ValueError("Unknown or missing original test in review")
            mapped.update(targets & named)
            covered.update(link["requirements"])
        if mapped != targets or covered != set(record["final_requirement_ids"]):
            raise ValueError("Incomplete source or grading mapping")
        evaluator_index.append({"instance_id": iid, "dataset": DATASET, "revision": REVISION,
                                "config": "default", "split": "test", "docker_image": rows[iid]["docker_image"],
                                "grading_sha256": review["grading_sha256"]})
        if "merge_additions_for_primary" in plan:
            length_study.append(label(dict(record, scenario_id=record["scenario_id"] + ".u3")))
            record = merge_additions(record, plan["merge_additions_for_primary"])
        primary.append(label(record))
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
        folder = Path(tmp) / "pilot"
        folder.mkdir()
        write_jsonl(folder / "candidates.jsonl", primary)
        write_jsonl(folder / "length_comparison.jsonl", length_study)
        write_jsonl(folder / "evaluation_sources.jsonl", evaluator_index)
        save(folder / "manifest.json", {"dataset": DATASET, "revision": REVISION, "parquet_sha256": PARQUET_SHA256,
             "visibility": "author_controller_only", "candidate_count": len(primary),
             "length_comparison_count": len(length_study), "environment_validated_original_task_count": 0,
             "evaluation_sources_kind": "pinned_pro_v2_row_references", "solver_experiments": 0,
             "files": {p.name: digest(p) for p in sorted(folder.glob("*.jsonl"))}})
        if output.exists():
            if any(not (output / p.name).is_file() or p.read_bytes() != (output / p.name).read_bytes()
                   for p in folder.iterdir()):
                raise ValueError("Existing export differs. Use a new --output directory")
        else:
            folder.rename(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["inventory", "draft", "build"])
    parser.add_argument("parquet", type=Path)
    parser.add_argument("--runs", type=Path)
    parser.add_argument("--only", help="Draft one named plan in a separate author run")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", type=Path, default=HERE / "pilot_v1")
    args = parser.parse_args()
    rows = load_python_rows(args.parquet)
    plans = read(HERE / "plans.json")
    if args.command == "inventory":
        print(json.dumps(inventory(rows), indent=2))
    elif args.command == "draft":
        if args.only:
            plans = [p for p in plans if p["name"] == args.only]
            if not plans:
                parser.error("unknown plan name")
        draft(rows, plans, args.runs, args.live)
    else:
        build(rows, plans, args.output, args.parquet)


if __name__ == "__main__":
    main()
