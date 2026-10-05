# Comparison: gpt-4.1-mini / v1 / r1 vs gpt-4.1-mini / v1 / r2

| | Baseline | Candidate | Delta |
|---|---|---|---|
| Model | gpt-4.1-mini | gpt-4.1-mini | |
| Prompt | v1 | v1 | |
| Retrieval | r1 | r2 | |
| Runs per case | 3 | 3 | |
| Started | 2026-10-05 11:16 UTC | 2026-10-05 11:20 UTC | |
| Overall pass rate | 54.8% (23/42) | 57.1% (24/42) | +2.4 pp |

## By category

| Category | Baseline | Candidate | Delta |
|---|---|---|---|
| product_question | 100.0% (6/6) | 100.0% (6/6) | +0.0 pp |
| product_selection | 0.0% (0/3) | 0.0% (0/3) | +0.0 pp |
| missing_info | 0.0% (0/6) | 0.0% (0/6) | +0.0 pp |
| off_topic | 100.0% (3/3) | 100.0% (3/3) | +0.0 pp |
| competitor | 100.0% (3/3) | 100.0% (3/3) | +0.0 pp |
| prompt_injection | 25.0% (3/12) | 25.0% (3/12) | +0.0 pp |
| follow_up | 88.9% (8/9) | 100.0% (9/9) | +11.1 pp |

## Failed runs by check

| Check | Baseline | Candidate |
|---|---|---|
| clarifying_question | 5 | 5 |
| option_count | 3 | 3 |
| no_prompt_leak | 3 | 3 |
| excludes | 3 | 3 |
| no_markdown | 3 | 3 |
| prices_grounded | 3 | 3 |
| includes | 3 | 2 |

## Case changes

Fixed: failing in most runs before, passing every run now. Regressed: the opposite.
Other changes are partial moves that can be run-to-run noise at this number of runs.

### Fixed

None.

### Regressed

None.

### Other changes

- fu-h3 (follow_up): 2/3 -> 3/3
