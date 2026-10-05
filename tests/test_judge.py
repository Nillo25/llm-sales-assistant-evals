from evals.cases import EvalCase, Expectations, Suite
from evals.checks import CheckResult
from evals.judge import (
    METRICS_BY_CATEGORY,
    JudgeMeta,
    ScoreResult,
    agreement,
    judge_input,
    judge_results,
    render_judge_report,
    summarize_judgments,
)
from evals.runner import RunResult
from sales_assistant.catalog import load_catalog, load_faq
from sales_assistant.retriever import build_context

CATALOG = load_catalog()
FAQ = load_faq()

FOLLOW_UP = EvalCase(
    id="fu-01",
    category="follow_up",
    question="What colors does it come in?",
    history=(("user", "Do you have a 10K power bank?"), ("assistant", "Yes, the 10K with Stand, $54.99.")),
)
OFF_TOPIC = EvalCase(id="ot-01", category="off_topic", question="Weather?", expect=Expectations(no_answer=True))
SUITE = Suite(competitor_brands=(), cases=(FOLLOW_UP, OFF_TOPIC))


def result(case, run, text, passed=True):
    checks = (CheckResult("includes", passed, "" if passed else "missing: blue"),)
    return RunResult(case.id, case.category, case.question, run, text=text, checks=checks)


RESULTS = [
    result(FOLLOW_UP, 1, "It comes in black.", passed=False),
    result(FOLLOW_UP, 2, "Black and Blue."),
    result(OFF_TOPIC, 1, "Sorry, I can only help with Ampwise."),
]


def fake_scorer(metric, ji):
    # The follow-up reply that invented a color is unfaithful; everything else passes.
    if metric == "faithfulness" and "black." in ji.actual_output and "Blue" not in ji.actual_output:
        return ScoreResult(score=0.5, threshold=0.9, passed=False, reason="'black only' is not in the context", cost=0.01)
    return ScoreResult(score=1.0, threshold=0.7, passed=True, reason="ok", cost=0.01)


def test_each_category_gets_metrics_and_refusals_get_role_checks_only():
    assert set(METRICS_BY_CATEGORY) == {
        "product_question", "product_selection", "missing_info", "off_topic", "competitor", "prompt_injection", "follow_up",
    }
    assert "honest_about_gaps" in METRICS_BY_CATEGORY["missing_info"]
    assert "answers_question" not in METRICS_BY_CATEGORY["missing_info"]
    # DeepEval's answer relevancy is calibration-only (see evals/judge.py).
    assert not any("answer_relevancy" in metrics for metrics in METRICS_BY_CATEGORY.values())
    assert METRICS_BY_CATEGORY["off_topic"] == ("stays_in_role",)


def test_judge_input_shows_the_dialog_and_counts_earlier_assistant_turns_as_context():
    ji = judge_input(FOLLOW_UP, "Black.", build_context(FOLLOW_UP.question, CATALOG, FAQ))
    assert ji.input.endswith("Customer's latest message: What colors does it come in?")
    assert "Customer: Do you have a 10K power bank?" in ji.input
    assert ji.retrieval_context[-1] == "Earlier in this conversation the assistant said: Yes, the 10K with Stand, $54.99."
    assert ji.actual_output == "Black."


def test_judge_input_without_history_is_just_the_question():
    ji = judge_input(OFF_TOPIC, "Sorry.", build_context(OFF_TOPIC.question, CATALOG, FAQ))
    assert ji.input == "Weather?"


def test_only_selected_runs_are_judged_with_the_category_metrics():
    judgments = judge_results(RESULTS, SUITE, products=CATALOG, faq=FAQ, scorer=fake_scorer, runs=(1,), workers=1)
    assert [(j.case_id, j.run, j.metric) for j in judgments] == [
        ("fu-01", 1, m) for m in METRICS_BY_CATEGORY["follow_up"]
    ] + [("ot-01", 1, "stays_in_role")]


def test_scorer_errors_are_recorded_not_raised():
    def broken(metric, ji):
        raise RuntimeError("judge timeout")

    judgments = judge_results(RESULTS[2:], SUITE, products=CATALOG, faq=FAQ, scorer=broken, runs=(1,), workers=1)
    assert judgments[0].error == "RuntimeError: judge timeout"
    assert judgments[0].score is None


def test_summary_and_agreement_with_deterministic_checks():
    judgments = judge_results(RESULTS, SUITE, products=CATALOG, faq=FAQ, scorer=fake_scorer, runs=(1, 2), workers=1)
    rows = {(s.category, s.metric): s for s in summarize_judgments(judgments)}
    faith = rows[("follow_up", "faithfulness")]
    assert (faith.passed, faith.total, faith.mean_score) == (1, 2, 0.75)
    agree = agreement(RESULTS, judgments)
    assert (agree.both_pass, agree.both_fail) == (2, 1)
    assert agree.checks_only == [] and agree.judge_only == []


def test_judge_report_lists_rates_agreement_cost_and_failed_judgments():
    judgments = judge_results(RESULTS, SUITE, products=CATALOG, faq=FAQ, scorer=fake_scorer, runs=(1, 2), workers=1)
    meta = JudgeMeta(source="2026-10-05_m_v1", sut_model="m", prompt_version="v1", judge_model="j", runs=(1, 2), duration_s=3)
    report = render_judge_report(judgments, RESULTS, meta)
    assert "Judge: j (DeepEval)" in report
    assert "| follow_up | 1/2 (0.75) |" in report
    assert "| Judge pass | 2 | 0 |" in report
    assert "Judge cost: $0.07" in report
    assert "### fu-01 run 1 (follow_up)" in report
    assert "faithfulness 0.50 < 0.90: 'black only' is not in the context" in report
    report.encode("ascii")


def test_rate_limited_calls_are_retried_with_backoff():
    from evals.judge import with_backoff

    calls, sleeps = [], []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("RetryError[... raised RateLimitError>]")
        return "ok"

    assert with_backoff(flaky, delays=(1, 2, 4), sleep=sleeps.append) == "ok"
    assert sleeps == [1, 2]


def test_other_errors_and_exhausted_retries_are_raised():
    import pytest

    from evals.judge import with_backoff

    def broken():
        raise ValueError("bad input")

    with pytest.raises(ValueError):
        with_backoff(broken, delays=(1,), sleep=lambda s: None)

    def always_limited():
        raise RuntimeError("RateLimitError")

    with pytest.raises(RuntimeError):
        with_backoff(always_limited, delays=(1, 2), sleep=lambda s: None)


def test_timeouts_are_retried_too():
    from evals.judge import with_backoff

    calls = []

    def slow_then_ok():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("RetryError[<Future ... raised TimeoutError>]")
        return "ok"

    assert with_backoff(slow_then_ok, delays=(1,), sleep=lambda s: None) == "ok"


def test_already_judged_pairs_are_skipped_and_each_new_judgment_is_reported():
    seen = []
    judgments = judge_results(
        RESULTS,
        SUITE,
        products=CATALOG,
        faq=FAQ,
        scorer=fake_scorer,
        runs=(1,),
        workers=1,
        skip={("fu-01", 1, "faithfulness"), ("fu-01", 1, "answers_question")},
        on_judgment=seen.append,
    )
    assert [(j.case_id, j.metric) for j in judgments] == [("fu-01", "no_invented_facts"), ("ot-01", "stays_in_role")]
    assert seen == judgments
