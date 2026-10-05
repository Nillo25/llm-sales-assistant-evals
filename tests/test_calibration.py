import textwrap

import pytest

from evals.calibration import load_calibration, render_calibration_report, run_calibration
from evals.cases import load_suite
from evals.judge import ALL_METRICS, ScoreResult
from sales_assistant.catalog import load_catalog, load_faq

SUITE = load_suite()


def write(tmp_path, body):
    path = tmp_path / "cal.yaml"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


ITEMS = """
- id: cal-01
  case: fu-01
  retrieved: []
  reply: It is available in black.
  expected: {no_invented_facts: fail, answer_relevancy: pass}
- id: cal-02
  case: pq-03
  retrieved: [AW-WS-3IN1]
  reply: It costs $99.99.
  expected: {no_invented_facts: pass}
"""


def test_bundled_calibration_set_is_valid_and_covers_every_metric():
    items = load_calibration(SUITE, products=load_catalog())
    assert len(items) >= 10
    covered = {m for item in items for m in item.expected}
    assert covered == set(ALL_METRICS)
    # Both verdicts must be represented, or agreement could be reached by always saying "pass".
    for metric in covered:
        labels = {item.expected[metric] for item in items if metric in item.expected}
        assert labels == {True, False}, metric


def test_labels_are_parsed_as_booleans(tmp_path):
    items = load_calibration(SUITE, write(tmp_path, ITEMS), products=load_catalog())
    assert items[0].case_id == "fu-01"
    assert (items[0].retrieved, items[1].retrieved) == ((), ("AW-WS-3IN1",))
    assert items[0].expected == {"no_invented_facts": False, "answer_relevancy": True}


@pytest.mark.parametrize(
    "bad, message",
    [
        (ITEMS.replace("case: fu-01", "case: zz-99"), "cal-01.*zz-99"),
        (ITEMS.replace("answer_relevancy: pass", "politeness: pass"), "cal-01.*politeness"),
        (ITEMS.replace("answer_relevancy: pass", "answer_relevancy: maybe"), "cal-01.*maybe"),
        (ITEMS.replace("id: cal-02", "id: cal-01"), "duplicate.*cal-01"),
        (ITEMS.replace("retrieved: [AW-WS-3IN1]", "retrieved: [AW-NOPE]"), "cal-02.*AW-NOPE"),
        (ITEMS.replace("  retrieved: []\n", ""), "cal-01.*retrieved"),
    ],
)
def test_invalid_items_are_rejected(tmp_path, bad, message):
    with pytest.raises(ValueError, match=message):
        load_calibration(SUITE, write(tmp_path, bad), products=load_catalog())


def judge_saying(verdicts):
    def scorer(metric, ji):
        ok = verdicts[(ji.actual_output, metric)]
        return ScoreResult(score=0.9 if ok else 0.2, threshold=0.7, passed=ok, reason=f"{metric} says {ok}")
    return scorer


def test_agreement_false_alarms_and_misses(tmp_path):
    items = load_calibration(SUITE, write(tmp_path, ITEMS), products=load_catalog())
    scorer = judge_saying({
        ("It is available in black.", "no_invented_facts"): True,     # miss: should have failed
        ("It is available in black.", "answer_relevancy"): True,      # agrees
        ("It costs $99.99.", "no_invented_facts"): False,             # false alarm
    })
    results = run_calibration(items, SUITE, products=load_catalog(), faq=load_faq(), scorer=scorer, workers=1)
    assert [(r.item_id, r.metric, r.agrees) for r in results] == [
        ("cal-01", "no_invented_facts", False),
        ("cal-01", "answer_relevancy", True),
        ("cal-02", "no_invented_facts", False),
    ]
    report = render_calibration_report(results, judge_model="j", variant="default")
    assert "| no_invented_facts | 0/2 | 1 | 1 |" in report
    assert "| answer_relevancy | 1/1 | 0 | 0 |" in report
    assert "- cal-01 no_invented_facts: expected fail, judge passed (0.90)" in report
    report.encode("ascii")
