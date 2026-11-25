# Output guard replay: claude-haiku-5-5 / v2 / r2 vs claude-haiku-5-5 / v2 / r2

| | Baseline | Candidate | Delta |
|---|---|---|---|
| Model | claude-haiku-5-5 | claude-haiku-5-5 | |
| Prompt | v2 | v2 | |
| Retrieval | r2 | r2 | |
| Runs per case | 3 | 3 | |
| Started | 2026-11-25 08:58 UTC | 2026-11-25 08:58 UTC | |
| Overall pass rate | 89.3% (184/206) | 89.3% (184/206) | +0.0 pp |

Delta on the 43 shared cases, 95% interval (paired case bootstrap): [+0.0, +0.0], **within noise**.
The bootstrap redraws the same cases for both runs, so how hard each case is cancels out.
'Within noise' means this many cases and runs cannot tell the two configurations apart.

## By category

| Category | Baseline | Candidate | Delta | 95% interval | Verdict |
|---|---|---|---|---|---|
| product_question | 100.0% (24/24) | 100.0% (24/24) | +0.0 pp | [+0.0, +0.0] | within noise |
| product_selection | 80.0% (20/25) | 80.0% (20/25) | +0.0 pp | [+0.0, +0.0] | within noise |
| missing_info | 80.0% (20/25) | 80.0% (20/25) | +0.0 pp | [+0.0, +0.0] | within noise |
| off_topic | 100.0% (15/15) | 100.0% (15/15) | +0.0 pp | [+0.0, +0.0] | within noise |
| competitor | 90.9% (20/22) | 90.9% (20/22) | +0.0 pp | [+0.0, +0.0] | within noise |
| prompt_injection | 87.5% (70/80) | 87.5% (70/80) | +0.0 pp | [+0.0, +0.0] | within noise |
| follow_up | 100.0% (15/15) | 100.0% (15/15) | +0.0 pp | [+0.0, +0.0] | within noise |

## Failed runs by check

| Check | Baseline | Candidate |
|---|---|---|
| no_competitor_brands | 10 | 10 |
| option_count | 5 | 5 |
| includes | 5 | 5 |
| no_answer_flag | 2 | 2 |

## Case changes

Fixed: failing in most runs before, passing every run now. Regressed: the opposite.
Other changes are partial moves that can be run-to-run noise at this number of runs.

### Fixed

None.

### Regressed

None.

### Other changes

None.

## What the guard changed

Candidate = the same stored replies after the guard. A change to a reply that passed
every check is a possible false alarm and is marked.

Nothing.
