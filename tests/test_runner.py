import itertools

from evals.cases import EvalCase, Expectations, Suite
from dataclasses import replace

from evals.runner import RunMeta, dump_run, load_run, render_report, rescore, run_suite, summarize
from sales_assistant.catalog import load_catalog, load_faq
from sales_assistant.client import ModelReply

SUITE = Suite(
    competitor_brands=("Anker",),
    cases=(
        EvalCase(id="pq-01", category="product_question", question="How much is the 3-in-1 station?",
                 expect=Expectations(includes=(r"99\.99",))),
        EvalCase(id="ot-01", category="off_topic", question="Weather in Paris?",
                 expect=Expectations(no_answer=True)),
        EvalCase(id="co-01", category="competitor", question="Is Anker better?"),
    ),
)

REPLIES = {
    "How much is the 3-in-1 station?": itertools.repeat("It costs $99.99."),
    # Flaky: forgets the marker on the second run.
    "Weather in Paris?": itertools.cycle(["NO_ANSWER\nSorry.", "Sorry.", "NO_ANSWER\nSorry."]),
    "Is Anker better?": itertools.repeat("Anker is good, but try the Ampwise 10K.\u2019"),
}


class ScriptedResponder:
    def __init__(self, replies):
        self.replies = {q: iter(r) for q, r in replies.items()}

    def __call__(self, payload):
        question = payload["input"][-1]["content"][0]["text"]
        return ModelReply(raw=next(self.replies[question]), input_tokens=100, output_tokens=10, latency_s=0.1)


def run(responder=None, runs=3):
    return run_suite(
        SUITE,
        responder=responder or ScriptedResponder(REPLIES),
        model="m",
        prompt_version="v1",
        runs=runs,
        workers=1,
        products=load_catalog(),
        faq=load_faq(),
    )


def test_every_case_runs_n_times_in_case_order():
    results = run()
    assert [(r.case_id, r.run) for r in results] == [
        ("pq-01", 1), ("pq-01", 2), ("pq-01", 3),
        ("ot-01", 1), ("ot-01", 2), ("ot-01", 3),
        ("co-01", 1), ("co-01", 2), ("co-01", 3),
    ]


def test_pass_rates_and_stability_per_category():
    summary = summarize(run())
    cats = {c.category: c for c in summary.categories}
    assert (cats["product_question"].passed_runs, cats["product_question"].total_runs) == (3, 3)
    assert (cats["off_topic"].passed_runs, cats["off_topic"].flaky) == (2, 1)
    assert (cats["competitor"].passed_runs, cats["competitor"].stable_fail) == (0, 1)
    assert (summary.passed_runs, summary.total_runs) == (5, 9)
    assert summary.check_failures["no_answer_flag"] == (1, ("ot-01",))
    assert summary.check_failures["no_competitor_brands"] == (3, ("co-01",))
    assert (summary.input_tokens, summary.output_tokens) == (900, 90)


def test_api_errors_are_recorded_apart_from_failures_and_redacted():
    def broken(payload):
        raise RuntimeError("Incorrect API key provided: sk-proj-abc123XYZ")

    summary = summarize(run(responder=broken, runs=1))
    assert summary.errors == 3
    assert summary.total_runs == 0
    errors = [r.error for r in run(responder=broken, runs=1)]
    assert all("sk-proj-abc123XYZ" not in e and "RuntimeError" in e for e in errors)


def test_report_shows_meta_categories_failed_checks_and_failing_cases():
    report = render_report(summarize(run()), RunMeta(model="m", prompt_version="v1", runs=3, started_at="2026-10-05 10:00 UTC", duration_s=12.3))
    assert "Model: m" in report and "Prompt: v1" in report and "Runs per case: 3" in report
    assert "| off_topic | 1 | 66.7% (2/3) | 0 | 1 | 0 |" in report
    assert "| no_competitor_brands | 3 | co-01 |" in report
    assert "### co-01 (competitor): 0/3" in report
    assert "found: Anker" in report
    assert "Retrieved: none (catalog overview)" in report
    assert "pq-01" not in report.split("## Cases with failures")[1]


def test_report_is_plain_ascii_even_when_replies_are_not():
    report = render_report(summarize(run()), RunMeta(model="m", prompt_version="v1", runs=3, started_at="t", duration_s=1))
    report.encode("ascii")


META = RunMeta(model="m", prompt_version="v1", runs=3, started_at="2026-10-05 10:00 UTC", duration_s=12.3)


def test_raw_run_round_trips_through_json():
    import json

    results = run()
    meta, loaded = load_run(json.loads(json.dumps(dump_run(META, results))))
    assert meta == META
    assert loaded == results


def test_rescore_reapplies_current_checks_without_calling_the_model():
    results = run()
    stricter = replace(
        SUITE,
        cases=(replace(SUITE.cases[0], expect=Expectations(includes=(r"88\.88",))),) + SUITE.cases[1:],
    )
    rescored = rescore(results, stricter, products=load_catalog(), faq=load_faq(), prompt_version="v1")
    assert [r.text for r in rescored] == [r.text for r in results]
    assert summarize(rescored).check_failures["includes"] == (3, ("pq-01",))


def test_quality_gate():
    from evals.runner import below_threshold

    summary = summarize(run())  # 5 of 9 runs pass
    assert below_threshold(summary, 0.6)
    assert not below_threshold(summary, 0.5)
    assert not below_threshold(summary, None)
