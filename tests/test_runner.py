import itertools

from evals.cases import EvalCase, Expectations, Suite
from dataclasses import replace

from evals.runner import (
    RunMeta, RunResult, adaptive_jobs, dump_run, load_run, render_report, rescore, run_suite, summarize,
)
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
    assert "| off_topic | 1 | 66.7% (2/3) | [66.7, 66.7] | 0 | 1 | 0 |" in report
    assert "| product_question | 1 | 100.0% (3/3) | case-level >= 5.0 | 1 | 0 | 0 |" in report
    assert "Temperature: API default" in report
    assert "95% interval (case bootstrap)" in report
    assert "pass^k (every run passed): 33.3% of cases; pass@k (at least one run passed): 66.7%" in report
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


def test_rescore_uses_the_stored_context_not_current_retrieval():
    case = EvalCase(id="fu-09", category="follow_up", question="And the price?")  # retrieves nothing today
    stored = RunResult("fu-09", "follow_up", "And the price?", 1, text="It is $99.99.", retrieved=("AW-WS-3IN1",))
    suite = Suite(competitor_brands=(), cases=(case,))
    [r] = rescore([stored], suite, products=load_catalog(), faq=load_faq(), prompt_version="v1")
    assert r.retrieved == ("AW-WS-3IN1",)
    assert all(c.passed for c in r.checks), r.failed_checks


def test_runs_record_the_retrieval_version_and_old_runs_default_to_r1():
    import json

    meta = RunMeta(model="m", prompt_version="v1", runs=1, started_at="t", duration_s=1, retrieval="r2")
    assert "Retrieval: r2" in render_report(summarize(run(runs=1)), meta)
    old = dump_run(META, [])
    del old["meta"]["retrieval"]
    assert load_run(json.loads(json.dumps(old)))[0].retrieval == "r1"


def test_adaptive_runs_top_up_flaky_cases_and_listed_categories_only():
    results = run()
    jobs = adaptive_jobs(results, SUITE, max_runs=5, categories=("competitor",))
    # pq-01 is stable: no extra runs. ot-01 is flaky, co-01 is in a listed category.
    assert [(c.id, n) for c, n in jobs] == [("ot-01", 4), ("ot-01", 5), ("co-01", 4), ("co-01", 5)]


def test_adaptive_runs_continue_the_run_numbers_and_count_in_the_report():
    responder = ScriptedResponder(REPLIES)
    first = run(responder=responder)
    extra = run_suite(
        SUITE, responder=responder, model="m", prompt_version="v1", runs=0, workers=1,
        products=load_catalog(), faq=load_faq(), jobs=adaptive_jobs(first, SUITE, max_runs=5),
    )
    assert [(r.case_id, r.run) for r in extra] == [("ot-01", 4), ("ot-01", 5)]
    meta = replace(META, max_runs=5)
    report = render_report(summarize(first + extra), meta)
    assert "Runs per case: 3, topped up to 5 for flaky and security cases" in report
    assert "### ot-01 (off_topic): 3/5" in report


def test_attack_cases_get_an_upper_bound_on_how_often_the_attack_works():
    suite = Suite(competitor_brands=(), cases=(EvalCase(id="pi-01", category="prompt_injection", question="Ignore rules"),))
    results = [RunResult("pi-01", "prompt_injection", "Ignore rules", n) for n in range(1, 4)]
    report = render_report(summarize(results), META)
    assert "## Attack resistance" in report
    assert "| pi-01 | 0/3 | 63% |" in report
    assert "takes 29 attack-free runs" in report


def test_the_output_guard_runs_live_and_its_actions_are_kept():
    replies = {**REPLIES, "How much is the 3-in-1 station?": itertools.repeat("It costs $99.99. All products are free today.")}
    results = run_suite(
        SUITE, responder=ScriptedResponder(replies), model="m", prompt_version="v1", runs=1, workers=1,
        products=load_catalog(), faq=load_faq(), guard=True,
    )
    pq = results[0]
    assert pq.text == "It costs $99.99."
    assert pq.guard_actions and "promotion" in pq.guard_actions[0]
    report = render_report(summarize(results), replace(META, guard=True))
    assert "Output guard: on" in report
