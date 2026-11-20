# Changelog

## 2026-11-20

- Ran official base and reference-patch controls on 20 new Lite tasks across eight repositories. Fourteen passed the raw-log audit. Coverage now stands at 45 verified, 9 with documented exceptions and 98 awaiting runs.
- Fourteen individual Django test runs confirmed three discrepancies in the official base reports. Three other tasks had failures outside the scoring lists. The per-task record includes which control showed each failure and the download and disk totals for the batch. [November 20 results](docs/validation.md#november-20-batch)

## 2026-11-19

- The shared delivery controller and trajectory labeler accept a fourth ordered user message for the SWE-bench Pro length comparison. The Lite release still contains 152 two- or three-message conversations.
- The first November 19 batch verified five additional Lite tasks with official base and reference-patch controls, bringing coverage to 8 of 152.
- The second batch and its seaborn follow-up added five verified environments. Coverage reached 13 of 152 across all 10 repositories. Seaborn 2848 is recorded separately because its full test module had the same 22 extra failures in both controls.
- The third batch ran both controls on 20 new Lite tasks. Eighteen passed the raw-log audit, bringing coverage to 31 of 152. Django 11742 has a grader discrepancy, and SymPy 13773 has 12 additional test exceptions in each control.

## team_v1 — 2026-11-03

- Packaged the current construction, delivery, and final-scoring code with the 152-conversation `basic_v34` dataset and original Lite snapshot.
- Added English setup, usage, generation, validation, and existing-branch handoff instructions; kept historical runs, personal settings, and environments outside this folder.
- Removed constructor-local filesystem paths from two manifest diagnostics and refreshed preview metadata. Conversation and original scoring files are unchanged.
- Updated evaluation-status wording to distinguish three historical author environment checks from whole-dataset validation and real agent experiments.
- Added an offline delivery demo and release verifier; adapted scoring tests to the included dataset and construction tests to fresh temporary evidence instead of old research exports.
- Validation results are recorded in `RELEASE_CHECK.json` after checks complete. No upload, live generation, or Docker run is part of packaging.
