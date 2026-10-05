from evals.checks import CheckResult
from evals.compare import compare, render_comparison
from evals.runner import RunMeta, RunResult


def runs(case_id, category, outcomes, failing_check="includes"):
    """outcomes: one bool per run (True = pass)."""
    out = []
    for i, ok in enumerate(outcomes, start=1):
        checks = (CheckResult("no_markdown", True), CheckResult(failing_check, ok, "" if ok else "boom"))
        out.append(RunResult(case_id, category, f"q {case_id}", i, text="t", checks=checks))
    return out


BASE = (
    runs("fu-01", "follow_up", [False, False, False])          # fixed
    + runs("pq-01", "product_question", [True, True, True])    # regressed
    + runs("pi-03", "prompt_injection", [False, True, False])  # flaky movement
    + runs("ot-01", "off_topic", [True, True, True])           # unchanged
)
CAND = (
    runs("fu-01", "follow_up", [True, True, True])
    + runs("pq-01", "product_question", [False, False, True], failing_check="prices_grounded")
    + runs("pi-03", "prompt_injection", [True, True, False])
    + runs("ot-01", "off_topic", [True, True, True])
)


def test_overall_and_category_rates():
    cmp = compare(BASE, CAND)
    assert (cmp.base_passed, cmp.base_total, cmp.cand_passed, cmp.cand_total) == (7, 12, 9, 12)
    cats = {c.category: c for c in cmp.categories}
    assert (cats["follow_up"].base_passed, cats["follow_up"].cand_passed) == (0, 3)
    assert (cats["product_question"].base_passed, cats["product_question"].cand_passed) == (3, 1)


def test_failed_runs_per_check_on_both_sides():
    checks = {c.name: c for c in compare(BASE, CAND).checks}
    assert (checks["includes"].base_failed, checks["includes"].cand_failed) == (5, 1)
    assert (checks["prices_grounded"].base_failed, checks["prices_grounded"].cand_failed) == (0, 2)


def test_case_changes_are_classified():
    changes = {c.case_id: c for c in compare(BASE, CAND).changes}
    assert changes["fu-01"].kind == "fixed"
    assert changes["pq-01"].kind == "regressed"
    assert changes["pi-03"].kind == "changed"
    assert "ot-01" not in changes


def test_report():
    base_meta = RunMeta("gpt-a", "v1", 3, "2026-10-05 07:00 UTC", 60)
    cand_meta = RunMeta("gpt-b", "v1", 3, "2026-10-05 08:00 UTC", 70)
    report = render_comparison(compare(BASE, CAND), base_meta, cand_meta)
    assert report.startswith("# Comparison: gpt-a / v1 vs gpt-b / v1")
    assert "| Overall pass rate | 58.3% (7/12) | 75.0% (9/12) | +16.7 pp |" in report
    assert "| follow_up | 0.0% (0/3) | 100.0% (3/3) | +100.0 pp |" in report
    assert "| prices_grounded | 0 | 2 |" in report
    assert "- fu-01 (follow_up): 0/3 -> 3/3" in report.split("### Fixed")[1].split("###")[0]
    assert "- pq-01 (product_question): 3/3 -> 1/3" in report.split("### Regressed")[1].split("###")[0]
    assert "- pi-03 (prompt_injection): 1/3 -> 2/3" in report.split("### Other changes")[1]
    report.encode("ascii")
