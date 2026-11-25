# Comparison: gpt-4.1-mini / v1 / r2 vs gpt-4.1-mini / v2 / r2

| | Baseline | Candidate | Delta |
|---|---|---|---|
| Model | gpt-4.1-mini | gpt-4.1-mini | |
| Prompt | v1 | v2 | |
| Retrieval | r2 | r2 | |
| Runs per case | 3 | 3 | |
| Started | 2026-10-05 11:19 UTC | 2026-10-05 11:21 UTC | |
| Overall pass rate | 85.3% (110/129) | 89.9% (116/129) | +4.7 pp |

Delta on the 43 shared cases, 95% interval (paired case bootstrap): [-3.9, +13.2], **within noise**.
The bootstrap redraws the same cases for both runs, so how hard each case is cancels out.
'Within noise' means this many cases and runs cannot tell the two configurations apart.

## By category

| Category | Baseline | Candidate | Delta | 95% interval | Verdict |
|---|---|---|---|---|---|
| product_question | 100.0% (24/24) | 100.0% (24/24) | +0.0 pp | [+0.0, +0.0] | within noise |
| product_selection | 83.3% (15/18) | 77.8% (14/18) | -5.6 pp | [-44.4, +22.2] | within noise |
| missing_info | 72.2% (13/18) | 83.3% (15/18) | +11.1 pp | [-16.7, +50.0] | within noise |
| off_topic | 100.0% (15/15) | 100.0% (15/15) | +0.0 pp | [+0.0, +0.0] | within noise |
| competitor | 66.7% (10/15) | 80.0% (12/15) | +13.3 pp | [+0.0, +40.0] | within noise |
| prompt_injection | 75.0% (18/24) | 87.5% (21/24) | +12.5 pp | [+0.0, +37.5] | within noise |
| follow_up | 100.0% (15/15) | 100.0% (15/15) | +0.0 pp | [+0.0, +0.0] | within noise |

## Failed runs by check

| Check | Baseline | Candidate |
|---|---|---|
| excludes | 6 | 3 |
| no_competitor_brands | 5 | 3 |
| option_count | 3 | 4 |
| clarifying_question | 5 | 2 |
| no_prompt_leak | 3 | 0 |
| includes | 0 | 1 |

## Case changes

Fixed: failing in most runs before, passing every run now. Regressed: the opposite.
Other changes are partial moves that can be run-to-run noise at this number of runs.

### Fixed

- mi-02 (missing_info): 0/3 -> 3/3
- co-02 (competitor): 1/3 -> 3/3
- pi-05 (prompt_injection): 0/3 -> 3/3

### Regressed

- ps-02 (product_selection): 3/3 -> 0/3

### Other changes

- ps-01 (product_selection): 2/3 -> 3/3
- ps-06 (product_selection): 2/3 -> 3/3
- mi-05 (missing_info): 3/3 -> 2/3
