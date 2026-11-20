# Changelog

## 2026-11-19

- The shared delivery controller and trajectory labeler accept a fourth ordered user message for the SWE-bench Pro length comparison. The Lite release still contains 152 two- or three-message conversations.
- The first November 19 batch verified five additional Lite tasks with official base and reference-patch controls, bringing coverage to 8 of 152.
- The second batch and its seaborn follow-up added five verified environments. Coverage reached 13 of 152 across all 10 repositories. Seaborn 2848 is recorded separately because its full test module had the same 22 extra failures in both controls.

## team_v1 — 2026-11-03

- Packaged the current construction, delivery, and final-scoring code with the 152-conversation `basic_v34` dataset and original Lite snapshot.
- Added English setup, usage, generation, validation, and existing-branch handoff instructions; kept historical runs, personal settings, and environments outside this folder.
- Removed constructor-local filesystem paths from two manifest diagnostics and refreshed preview metadata. Conversation and original scoring files are unchanged.
- Updated evaluation-status wording to distinguish three historical author environment checks from whole-dataset validation and real agent experiments.
- Added an offline delivery demo and release verifier; adapted scoring tests to the included dataset and construction tests to fresh temporary evidence instead of old research exports.
- Validation results are recorded in `RELEASE_CHECK.json` after checks complete. No upload, live generation, or Docker run is part of packaging.
