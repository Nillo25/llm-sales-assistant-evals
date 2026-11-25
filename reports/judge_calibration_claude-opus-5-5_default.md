# Judge calibration: claude-opus-5-5 (default faithfulness)

- Agreement with human labels: 39/43, Cohen's kappa 0.81
- False alarm: the human says pass, the judge fails it. Miss: the human says fail, the judge passes it.
- Kappa corrects agreement for chance: 1 is perfect, 0 is no better than guessing from the base rate.
- Judge cost: $0.76

| Metric | Agreement | Kappa | False alarms | Misses |
|---|---|---|---|---|
| faithfulness | 5/7 | 0.00 | 0 | 2 |
| answer_relevancy | 3/5 | 0.29 | 2 | 0 |
| answers_question | 8/8 | 1.00 | 0 | 0 |
| no_invented_facts | 12/12 | 1.00 | 0 | 0 |
| honest_about_gaps | 5/5 | 1.00 | 0 | 0 |
| stays_in_role | 6/6 | 1.00 | 0 | 0 |

## Disagreements

- cal-01 faithfulness: expected fail, judge passed (1.00)
  > The score is 1.00 because there are no contradictions; the actual output aligns fully with the retrieval context. Nicely done staying faithful to the source material.
- cal-01 answer_relevancy: expected pass, judge failed (0.67)
  > The score is 0.67 because the response addresses the customer's question about the colors of the Ampwise 10K Magnetic Power Bank, but it loses relevance by including information about other types of power banks, which the customer did not ask about. The core answer is on target, keeping the score moderately high, but the off-topic content prevents it from being higher.
- cal-03 answer_relevancy: expected pass, judge failed (0.60)
  > The score is 0.60 because the response does address the price of the 3-in-1 wireless charging station, but it also adds details that don't answer the question, such as the available color options and a follow-up offer. These extras dilute the focus on the price and keep the score from being higher.
- cal-07 faithfulness: expected fail, judge passed (1.00)
  > The score is 1.00 because there are no contradictions; the actual output aligns fully with the retrieval context. Nicely done!
