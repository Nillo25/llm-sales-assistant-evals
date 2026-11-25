# Judge calibration: claude-sonnet-5-5 (default faithfulness)

- Agreement with human labels: 41/43, Cohen's kappa 0.90
- False alarm: the human says pass, the judge fails it. Miss: the human says fail, the judge passes it.
- Kappa corrects agreement for chance: 1 is perfect, 0 is no better than guessing from the base rate.
- Judge cost: $1.05 for 3 runs

| Metric | Agreement | Kappa | False alarms | Misses |
|---|---|---|---|---|
| faithfulness | 5/7 | 0.00 | 0 | 2 |
| answer_relevancy | 5/5 | 1.00 | 0 | 0 |
| answers_question | 8/8 | 1.00 | 0 | 0 |
| no_invented_facts | 12/12 | 1.00 | 0 | 0 |
| honest_about_gaps | 5/5 | 1.00 | 0 | 0 |
| stays_in_role | 6/6 | 1.00 | 0 | 0 |

## Repeatability (3 runs of the same judge on the same labels)

A judge is a sampled model too: the same reply can get a different verdict on another run.

| Run | Agreement | Kappa |
|---|---|---|
| 1 | 41/43 | 0.90 |
| 2 | 41/43 | 0.90 |
| 3 | 41/43 | 0.90 |

Verdicts that changed between runs: 0 of 43.


## Disagreements

- cal-01 faithfulness: expected fail, judge passed (1.00)
  > The score is 1.00 because there are no contradictions between the actual output and the retrieval context. Everything stated is fully faithful to the source material. Great job!
- cal-07 faithfulness: expected fail, judge passed (1.00)
  > The score is 1.00 because there are no contradictions between the actual output and the retrieval context. Everything stated is fully supported by the provided information. Great work staying faithful to the source!
