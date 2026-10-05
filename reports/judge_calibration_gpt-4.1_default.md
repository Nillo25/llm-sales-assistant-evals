# Judge calibration: gpt-4.1 (default faithfulness)

- Agreement with human labels: 38/43
- False alarm: the human says pass, the judge fails it. Miss: the human says fail, the judge passes it.

| Metric | Agreement | False alarms | Misses |
|---|---|---|---|
| faithfulness | 5/7 | 0 | 2 |
| answer_relevancy | 3/5 | 2 | 0 |
| answers_question | 8/8 | 0 | 0 |
| no_invented_facts | 11/12 | 1 | 0 |
| honest_about_gaps | 5/5 | 0 | 0 |
| stays_in_role | 6/6 | 0 | 0 |

## Disagreements

- cal-01 faithfulness: expected fail, judge passed (1.00)
  > The score is 1.00 because there are no contradictions-great job staying true to the retrieval context!
- cal-01 answer_relevancy: expected pass, judge failed (0.33)
  > The score is 0.33 because the response did not address the customer's specific question about color options and instead provided generic or unrelated information. It is not lower because the response may still be somewhat related to the product, but it fails to directly answer the query about colors.
- cal-03 answer_relevancy: expected pass, judge failed (0.25)
  > The score is 0.25 because most of the response discussed features and details unrelated to the price, which was the specific question. Only a small portion, if any, addressed the actual price, so the answer is mostly irrelevant but not entirely off-topic.
- cal-07 faithfulness: expected fail, judge passed (1.00)
  > The score is 1.00 because there are no contradictions-great job staying true to the retrieval context!
- cal-20 no_invented_facts: expected pass, judge failed (0.65)
  > The output lists two Ampwise earbuds and provides factual statements about each: AirLite is lightweight, for everyday use, has Bluetooth 5.3, 6 hours battery, and no active noise cancelling; Pro ANC has active noise cancelling, Bluetooth 5.3 with multipoint, 8 hours battery (6 with ANC), wireless charging case, and IPX5 water resistance. All these details are supported by the product catalog. T...
