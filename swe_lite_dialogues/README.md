# SWE-bench Lite Dialogues

A small research pipeline that turns one SWE-bench Lite issue into one conversation with two or three user messages: **U0 → U1 → optional U2**. At the end, the effective requirements must match the original task. The final code patch is scored with the original SWE-bench tests.

This is a **team preview**, ready for inspecting the data and integrating an evaluator. It is not a claim that every task has passed Docker validation or that a general solving agent is included.

## What is included

| Item | Current result |
|---|---:|
| Original tasks attempted | 300 |
| Selected conversations | 152 |
| Two / three messages | 59 / 93 |
| Three-message share | 61.2% |
| Cumulative / Clarification / Revision / Mixed | 12 / 36 / 18 / 86 |
| Repositories represented | 10 |
| Author base/gold environment checks | 45 verified across all 10 repositories, 9 with documented exceptions, 98 awaiting runs |

The other 148 originals were not admitted to this preview. They are not extra samples or silently counted as successes. See [validation and limitations](docs/validation.md).

## Start here: no Docker or model account needed

Use **Python 3.10 or later**; the handoff was checked with Python 3.12. The scripts use Unix facilities, so use macOS, Linux, or WSL. If `python3 --version` shows an older version, install a supported Python and use that interpreter (for example `python3.12`) in the commands below. Run these commands from this folder:

```sh
python3 --version
python3 verify_release.py
python3 demo.py --instance django__django-12983
```

The first script checks file integrity, all 152 records, scripted message delivery, and final scoring-input preparation. The demo prints slugify's messages one at a time using simulated end-of-turn events. **Neither command solves a task, starts Docker, or calls a model.** No pip dependencies are needed for these commands.

Open [all conversation examples](split_pilot/benchmark_output/basic_v34/examples.md) to browse the data without running anything.

## Files to use

```text
swe_lite_dialogues/
  README.md                 Start here
  demo.py                   Show a conversation being delivered
  verify_release.py         Offline handoff checks
  requirements-eval.txt      Optional official evaluator dependency
  docs/                     Data, scoring, generation, and branch instructions
  split_pilot/
    source_batch.py         Run small generation batches with review stops
    source_dataset.py       Check requirements and export reviewed conversations
    delivery.py             Release only the messages currently due
    evaluate_benchmark.py   Prepare, run, and summarize final scoring
    prompts/                Versioned construction prompts
    data/                   Pinned original Lite snapshot; author only
    benchmark_output/basic_v34/  Latest selected data and original scoring rows
```

The remaining Python files support these entrypoints or provide offline tests. Earlier prompt versions are retained because snapshots and compatibility helpers reference them. Old experimental CLIs are not the recommended workflow.

## Choose your next step

- **Use the existing data:** [data format and final scoring](docs/usage.md).
- **Generate new conversations:** [generation workflow and review gates](docs/generation.md).
- **Add this folder to your team's existing repository:** [branch handoff](docs/branch-handoff.md).
- **Understand what has actually been validated:** [validation scope](docs/validation.md).
- **Check sources and bundled notices:** [third-party sources](THIRD_PARTY.md).

## Keep the solver separate

This folder is for the **author, delivery controller, and evaluator**. It contains future messages, reference patches, and hidden tests. Keep it outside the solving agent's filesystem/container. Give the agent only its clean source checkout and the transcript returned by `Delivery.visible_history()`. The controller and external evaluator retain the full dataset.

There is no general solver adapter in this handoff. A teammate must connect their chosen agent to `delivery.py` and save its final patch. Intermediate-stage scores are not reported in this preview.

## Offline regression checks

```sh
python3 -m unittest discover -s split_pilot -p 'test_*.py'
```

These tests use fixed fixtures and synthetic reports, including simulated generation. They do not spend model quota or run repository tests in Docker.
