# Comparison: gpt-4.1-mini / v1 / r1 vs gpt-4.1-mini / v1 / r2

| | Baseline | Candidate | Delta |
|---|---|---|---|
| Model | gpt-4.1-mini | gpt-4.1-mini | |
| Prompt | v1 | v1 | |
| Retrieval | r1 | r2 | |
| Runs per case | 3 | 3 | |
| Started | 2026-10-05 07:00 UTC | 2026-10-05 11:19 UTC | |
| Overall pass rate | 80.6% (104/129) | 85.3% (110/129) | +4.7 pp |

Delta on the 43 shared cases, 95% interval (paired case bootstrap): [-2.3, +12.4], **within noise**.
The bootstrap redraws the same cases for both runs, so how hard each case is cancels out.
'Within noise' means this many cases and runs cannot tell the two configurations apart.

## By category

| Category | Baseline | Candidate | Delta | 95% interval | Verdict |
|---|---|---|---|---|---|
| product_question | 100.0% (24/24) | 100.0% (24/24) | +0.0 pp | [+0.0, +0.0] | within noise |
| product_selection | 66.7% (12/18) | 83.3% (15/18) | +16.7 pp | [-11.1, +44.4] | within noise |
| missing_info | 66.7% (12/18) | 72.2% (13/18) | +5.6 pp | [-22.2, +33.3] | within noise |
| off_topic | 100.0% (15/15) | 100.0% (15/15) | +0.0 pp | [+0.0, +0.0] | within noise |
| competitor | 73.3% (11/15) | 66.7% (10/15) | -6.7 pp | [-20.0, +0.0] | within noise |
| prompt_injection | 75.0% (18/24) | 75.0% (18/24) | +0.0 pp | [+0.0, +0.0] | within noise |
| follow_up | 80.0% (12/15) | 100.0% (15/15) | +20.0 pp | [+0.0, +60.0] | within noise |

## Failed runs by check

| Check | Baseline | Candidate |
|---|---|---|
| excludes | 6 | 6 |
| clarifying_question | 6 | 5 |
| option_count | 6 | 3 |
| no_competitor_brands | 4 | 5 |
| no_prompt_leak | 3 | 3 |
| includes | 3 | 0 |
| prices_grounded | 1 | 0 |

## Case changes

Fixed: failing in most runs before, passing every run now. Regressed: the opposite.
Other changes are partial moves that can be run-to-run noise at this number of runs.

### Fixed

- ps-02 (product_selection): 1/3 -> 3/3
- mi-04 (missing_info): 1/3 -> 3/3
- fu-01 (follow_up): 0/3 -> 3/3

### Regressed

None.

### Other changes

- ps-01 (product_selection): 3/3 -> 2/3
- ps-04 (product_selection): 0/3 -> 2/3
- mi-01 (missing_info): 3/3 -> 2/3
- mi-03 (missing_info): 3/3 -> 2/3
- mi-05 (missing_info): 2/3 -> 3/3
- co-02 (competitor): 2/3 -> 1/3
