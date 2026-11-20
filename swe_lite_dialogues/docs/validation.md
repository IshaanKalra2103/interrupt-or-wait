# Validation scope and limitations

This is the first team handoff of `basic_v34`, not an all-task runtime certification.

| Layer | Evidence / status |
|---|---|
| Construction | All 300 originals attempted; 152 selected and 148 not selected. Historical author checks rebuilt the selected export and retained original scoring rows. |
| Handoff checks | File hashes, record identities, final annotation sets, scripted delivery, and scoring-input preparation are checked offline by `verify_release.py`. |
| Program tests | Fixed fixtures exercise generation review stops, category handling, delivery isolation, and scoring denominators. No model or Docker calls. |
| Author runtime | 13 of 152 tasks have verified base/gold controls across all 10 source repositories. One additional task has extra failures in both controls. The remaining 138 await runs. |
| Real agent experiments | No general solver adapter or new model scores are included. Scripted delivery and gold-patch tests are not agent success rates. |
| Intermediate stages | No dataset-wide intermediate score or per-stage gold requirement. Final scoring uses the original task tests. |

The first three author checks were completed before the team handoff.

| Original | Base target tests | Gold target tests | Named regression tests |
|---|---:|---:|---:|
| django__django-12983 (slugify) | 0/1 | 1/1 | 15/15 for both |
| django__django-14017 | 0/2 | 2/2 | 147/147 for both |
| sympy__sympy-20322 | 0/1 | 1/1 | 89/89 for both |

The latter two runs also checked the original issue examples. The frozen manifest records one environment at construction time. The November 3 statistics and preview record the three environments known at the time of the handoff.

On November 19, five further Lite tasks were selected for author checks across five repositories, four update types and both conversation lengths. The team's proposed five-task solver pilot had no published task IDs. Each original ran in its official amd64 image with the reference patch and with an unused text-file addition that lets the grader exercise the unmodified production code.

| Original | Base target tests | Gold target tests | Named regression tests |
|---|---:|---:|---:|
| astropy__astropy-12907 | 0/2 | 2/2 | 13/13 for both |
| django__django-11999 | 0/1 | 1/1 | 30/30 for both |
| pytest-dev__pytest-8365 | 0/1 | 1/1 | 32/32 for both |
| sphinx-doc__sphinx-8282 | 0/1 | 1/1 | 16/16 for both |
| sympy__sympy-12481 | 0/1 | 1/1 | 7/7 for both |

The raw logs account for all six named targets and 98 named regressions in both controls. The pytest module also skipped one test outside those lists. SymPy ran one additional passing test. This batch made zero solver calls. Image digests, original revisions, run IDs and log hashes are in the [November 19 runtime record](lite-environment-2026-11-19.json).

### Second November 19 batch

We selected one task from each of the five repositories that still lacked a verified environment and fixed the IDs before running the controls. We then checked one additional seaborn task after the first showed failures outside the official scoring lists.

| Sample | Original | Base targets | Gold targets | Named regressions in each control | Extra failures in each control |
|---|---|---:|---:|---:|---:|
| Planned | matplotlib__matplotlib-26020 | 0/1 | 1/1 | 48/48 | 0 |
| Planned | mwaskom__seaborn-2848 | 0/1 | 1/1 | 50/50 | 22 |
| Planned | pydata__xarray-5131 | 0/10 | 10/10 | 24/24 | 0 |
| Planned | pylint-dev__pylint-5859 | 0/1 | 1/1 | 10/10 | 0 |
| Planned | scikit-learn__scikit-learn-13779 | 0/2 | 2/2 | 18/18 | 0 |
| Follow-up | mwaskom__seaborn-3190 | 0/1 | 1/1 | 84/84 | 0 |

For seaborn 2848 the official grader marked the reference patch resolved. The full test module still failed the same 22 unscored tests on both the base and the reference patch. In the official image, 21 failures referenced the missing pandas 2.0.0 option `mode.use_inf_as_null` and one came from `pytest.warns(None)` on pytest 8.3.3. This task is tracked separately from the 13 verified environments.

The follow-up used the lowest remaining seaborn task ID, 3190. Both controls also reported one expected failure outside the scoring lists. All 12 Docker evaluations retained their original test lists and made zero solver calls. [Second-batch results and log hashes](lite-environment-2026-11-19-batch2.json)

Known limits are retained:

- Categories are uneven; Mixed accounts for 86/152 and many examples use a similar clarify-then-revise pattern.
- Some early messages ask for investigation or describe behavior already satisfied by the base. Not every round requires an independent code edit.
- The original tests sometimes cover a shared component rather than every detail of the issue text. Passing them is not proof of complete semantic equivalence.
- Semantic review was assistant-assisted, not independent certification. A six-task historical spot check found no new blocking issue; it was not a random estimate of error rate.
- Admitted records come from multiple frozen model/prompt versions. Dataset proportions are not a controlled comparison of model quality.
- The 148 non-selected tasks include source/test conflicts, weak splits, and execution failures. They may be reconsidered; no full exclusion ledger is included in this compact package.
- `swebench==4.1.0` is a compatibility baseline. Formal experiments should retain raw logs and separately investigate upstream grader limitations.

The original Lite snapshot, conversations and scoring rows retain their November 3 hashes. The packaging notes describe that first handoff. The changelog records the later shared-controller update and the November 19 environment checks. [Packaging notes](../PACKAGING.json) · [Changelog](../CHANGELOG.md)
