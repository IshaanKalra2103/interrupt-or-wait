# SWE-bench Pro V2 dialogue pilot

Five Python development tasks from three repositories use the same candidate reader, trajectory labels and delivery controller as the Lite handoff. Each original has one primary conversation. The tasks were chosen to examine different update types and lengths. The sample cannot estimate how often a particular type or length occurs in Pro.

| Original | Primary messages | Trajectory | What changes |
|---|---:|---|---|
| Ansible YAML dumper | 2 | Revision | Replace a temporary Ansible exception policy with the native Jinja exception. |
| Open Library import validation | 3 | Mixed | Add a second acceptance criterion, then clarify validation order and error selection. |
| Open Library table of contents | 3 | Cumulative | Format simple entries, support a metadata round trip, then preserve fields on database load. |
| qutebrowser WebKit error replies | 2 | Clarification | Investigate error notification, then specify the signal. U0 can be satisfied by investigation. |
| qutebrowser filesystem completion | 3 | Clarification | Specify the category and its public interface, then settle the empty-input and typed-directory policies. |

## Use the conversations

Keep this directory and its sibling `swe_lite_dialogues` on the controller side. Give the solver a clean upstream checkout and the history returned by `Delivery.visible_history()`. The candidate records include future messages and the complete final prompt. The original issue, requirements and interface appear verbatim in that final prompt, which Full receives upfront and the staged conditions receive with their last update.

From the team repository root, run the offline check with Python 3.10 or later.

```sh
python3 swe_pro_dialogues/verify_pilot.py
```

Load the five primaries from `swe_pro_dialogues/pilot_v1/candidates.jsonl`. With the Lite `split_pilot` directory on the Python import path, the existing interfaces work directly.

```python
from benchmark_data import load_candidates
from delivery import Delivery

records = load_candidates("swe_pro_dialogues/pilot_v1")
controller = Delivery(records[0], condition="wait")
public_history = controller.visible_history()
```

The extra record in `length_comparison.jsonl` shares its original task, final prompt, grading reference, wording order and category with the table-of-contents primary. The four messages cover base Markdown formatting, metadata serialization, Markdown parsing and loading from the database. Its three-message counterpart groups serialization and parsing in one message. Include both in a within-task length comparison and count the original once. The database-loading assertion is an upstream pass-to-pass test, so the extra message can matter to the specification even if the code already satisfies it.

## Rebuild or inspect the split

The loader pins the official default/test Parquet by revision and SHA-256. Use an author directory for the download. The shipped JSONL and the scripted verifier need only the Python standard library. Rebuilding also needs PyArrow, tested with version 26.0.0. [Pinned upstream dataset card](https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro/blob/2d52cb3df914a3fcf80c7f66738b3a88ae37fc50/README.md)

```sh
curl --fail --location --output pro-v2.parquet https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro/resolve/2d52cb3df914a3fcf80c7f66738b3a88ae37fc50/data/default/test-00000-of-00001.parquet
python3 swe_pro_dialogues/pilot.py inventory pro-v2.parquet
python3 swe_pro_dialogues/pilot.py build pro-v2.parquet --output /tmp/pro-dialogue-replay
python3 swe_pro_dialogues/verify_pilot.py /tmp/pro-dialogue-replay
```

The pinned split has 237 Python tasks. The median is six requirement items, with at least four items in 199 tasks. Numbered source items retain continuations and examples. Repeated clauses are grouped by behavior. The table-of-contents example has 18 items and four separable behaviors in the chosen plan.

`plans.json` records the author-designed groups, temporary policies and open questions. The existing tool-free construction model generated the English wording with the requested Sol/medium configuration. The author checked each draft against the public source, the original test assertions and the reference change. Two first drafts were held for scope or category ambiguity, then regenerated once each. `reviews.json` retains the accepted raw answers, hashes, review findings, coverage limits and the two held-answer hashes. The fixed plans differ in provenance from Lite's model-generated category plans. Running `pilot.py draft` previews these public inputs. Generation uses `--live --runs PATH` in a fresh author directory.

## Evaluation status

The offline verifier replays Full, Wait and Interrupt on all six records and checks each visible message prefix. `evaluation_sources.jsonl` identifies the pinned Pro grading rows and images. Use the official Pro V2 verifier for final patch evaluation. Source patches and hidden tests belong in the external evaluator. This pilot has zero local Pro base/gold runs, zero solver runs and no measured interruption timing or intermediate score. [Official Pro V2 evaluation tooling](https://github.com/scaleapi/SWE-bench_Pro-os/tree/main/v2)
