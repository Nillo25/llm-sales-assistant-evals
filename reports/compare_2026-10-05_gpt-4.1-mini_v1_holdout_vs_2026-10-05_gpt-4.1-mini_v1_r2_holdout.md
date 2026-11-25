# Comparison: gpt-4.1-mini / v1 / r1 vs gpt-4.1-mini / v1 / r2

| | Baseline | Candidate | Delta |
|---|---|---|---|
| Model | gpt-4.1-mini | gpt-4.1-mini | |
| Prompt | v1 | v1 | |
| Retrieval | r1 | r2 | |
| Runs per case | 3 | 3 | |
| Started | 2026-10-05 11:16 UTC | 2026-10-05 11:20 UTC | |
| Overall pass rate | 54.8% (23/42) | 57.1% (24/42) | +2.4 pp |

Delta on the 14 shared cases, 95% interval (paired case bootstrap): [+0.0, +7.1], **within noise**.
The bootstrap redraws the same cases for both runs, so how hard each case is cancels out.
'Within noise' means this many cases and runs cannot tell the two configurations apart.

## By category

| Category | Baseline | Candidate | Delta | 95% interval | Verdict |
|---|---|---|---|---|---|
| product_question | 100.0% (6/6) | 100.0% (6/6) | +0.0 pp | [+0.0, +0.0] | within noise |
| product_selection | 0.0% (0/3) | 0.0% (0/3) | +0.0 pp | [+0.0, +0.0] | within noise |
| missing_info | 0.0% (0/6) | 0.0% (0/6) | +0.0 pp | [+0.0, +0.0] | within noise |
| off_topic | 100.0% (3/3) | 100.0% (3/3) | +0.0 pp | [+0.0, +0.0] | within noise |
| competitor | 100.0% (3/3) | 100.0% (3/3) | +0.0 pp | [+0.0, +0.0] | within noise |
| prompt_injection | 25.0% (3/12) | 25.0% (3/12) | +0.0 pp | [+0.0, +0.0] | within noise |
| follow_up | 88.9% (8/9) | 100.0% (9/9) | +11.1 pp | [+0.0, +33.3] | within noise |

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
