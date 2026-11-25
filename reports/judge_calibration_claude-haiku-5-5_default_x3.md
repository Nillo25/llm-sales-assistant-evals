# Judge calibration: claude-haiku-5-5 (default faithfulness)

- Agreement with human labels: 39/43, Cohen's kappa 0.81
- False alarm: the human says pass, the judge fails it. Miss: the human says fail, the judge passes it.
- Kappa corrects agreement for chance: 1 is perfect, 0 is no better than guessing from the base rate.
- Judge cost: $0.06 for 3 runs

| Metric | Agreement | Kappa | False alarms | Misses |
|---|---|---|---|---|
| faithfulness | 5/7 | 0.00 | 0 | 2 |
| answer_relevancy | 3/5 | 0.29 | 2 | 0 |
| answers_question | 8/8 | 1.00 | 0 | 0 |
| no_invented_facts | 12/12 | 1.00 | 0 | 0 |
| honest_about_gaps | 5/5 | 1.00 | 0 | 0 |
| stays_in_role | 6/6 | 1.00 | 0 | 0 |

## Repeatability (3 runs of the same judge on the same labels)

A judge is a sampled model too: the same reply can get a different verdict on another run.

| Run | Agreement | Kappa |
|---|---|---|
| 1 | 39/43 | 0.81 |
| 2 | 38/43 | 0.76 |
| 3 | 39/43 | 0.81 |

Verdicts that changed between runs: 1 of 43.

- cal-02 answer_relevancy: pass, fail, pass

## Disagreements

- cal-01 faithfulness: expected fail, judge passed (1.00)
  > The score is 1.00 because no contradictions were found, meaning every claim in the actual output aligns with the retrieval context. Nicely done, the output stays fully faithful to its sources!
- cal-01 answer_relevancy: expected pass, judge failed (0.50)
  > The score is 0.50 because the actual output is only partly relevant to the customer's question about colors: one statement addresses a different power bank's help instead of the Ampwise 10K Magnetic Power Bank's color options, which pulls the score down and keeps it from being higher.
- cal-03 answer_relevancy: expected pass, judge failed (0.33)
  > The score is 0.33 because the actual output mostly fails to address the question about the price of the 3-in-1 wireless charging station. The irrelevant statements describe available colors and charging capabilities, which do not answer how much the product costs. Only a small portion of the output is relevant to the user's pricing question, so the score stays low.
- cal-07 faithfulness: expected fail, judge passed (1.00)
  > The score is 1.00 because no contradictions were found between the actual output and the retrieval context, so every claim in the response is fully supported by the provided information. Nicely done, the response stays faithful to its sources throughout.
