import pytest

from evals.stats import (
    case_bootstrap,
    cohen_kappa,
    failure_upper_bound,
    paired_bootstrap,
    pass_at_k,
    pass_hat_k,
    runs_needed,
    wilson,
)


def test_wilson_matches_the_textbook_value():
    # 8/10 at 95%: [0.490, 0.943] (Wilson score interval)
    i = wilson(8, 10)
    assert i.estimate == 0.8
    assert i.low == pytest.approx(0.490, abs=1e-3)
    assert i.high == pytest.approx(0.943, abs=1e-3)


def test_wilson_stays_inside_zero_and_one():
    assert wilson(0, 3).low == 0.0
    assert wilson(3, 3).high == 1.0


def test_zero_failures_in_three_runs_allows_a_63_percent_failure_rate():
    assert failure_upper_bound(0, 3) == pytest.approx(1 - 0.05 ** (1 / 3), abs=1e-6)
    assert failure_upper_bound(0, 3) == pytest.approx(0.632, abs=1e-3)


def test_failure_bound_shrinks_with_runs_and_grows_with_failures():
    assert failure_upper_bound(0, 30) == pytest.approx(0.095, abs=1e-3)
    assert failure_upper_bound(1, 30) > failure_upper_bound(0, 30)
    assert failure_upper_bound(3, 3) == 1.0


def test_runs_needed_for_a_ten_percent_bound():
    assert runs_needed(0.10) == 29
    assert failure_upper_bound(0, runs_needed(0.10)) <= 0.10


def test_case_bootstrap_brackets_the_pooled_rate_and_is_reproducible():
    counts = {f"c{i}": (3, 3) for i in range(30)} | {f"f{i}": (0, 3) for i in range(10)}
    a, b = case_bootstrap(counts, iterations=2000), case_bootstrap(counts, iterations=2000)
    assert a == b
    assert a.estimate == pytest.approx(0.75)
    assert a.low < 0.75 < a.high


def test_single_constant_case_has_no_spread():
    i = case_bootstrap({"c": (2, 3)}, iterations=200)
    assert (i.low, i.estimate, i.high) == pytest.approx((2 / 3, 2 / 3, 2 / 3))


def test_paired_bootstrap_sees_a_consistent_gain_as_real():
    base = {f"c{i}": (1, 3) for i in range(40)}
    cand = {f"c{i}": (3, 3) for i in range(40)}
    d = paired_bootstrap(base, cand, iterations=2000)
    assert d.estimate == pytest.approx(2 / 3)
    assert d.excludes_zero


def test_paired_bootstrap_calls_a_two_run_move_on_14_cases_noise():
    # The holdout situation: 23/42 -> 25/42 on 14 cases.
    base = {f"h{i}": (2, 3) for i in range(9)} | {f"h{i}": (1, 3) for i in range(9, 12)} | {"h12": (0, 3), "h13": (2, 3)}
    cand = dict(base) | {"h12": (1, 3), "h9": (2, 3)}
    d = paired_bootstrap(base, cand, iterations=2000)
    assert not d.excludes_zero


def test_paired_bootstrap_uses_only_shared_cases():
    d = paired_bootstrap({"a": (0, 3), "b": (3, 3)}, {"a": (3, 3), "z": (0, 3)}, iterations=100)
    assert d.estimate == 1.0
    with pytest.raises(ValueError):
        paired_bootstrap({"a": (0, 3)}, {"b": (0, 3)})


def test_pass_hat_k_and_pass_at_k():
    counts = {"stable": (3, 3), "flaky": (1, 3), "broken": (0, 3)}
    assert pass_hat_k(counts) == pytest.approx(1 / 3)
    assert pass_at_k(counts) == pytest.approx(2 / 3)


def test_cohen_kappa():
    assert cohen_kappa([(True, True), (False, False)] * 5) == 1.0
    assert cohen_kappa([(True, False), (False, True)] * 5) == -1.0
    assert cohen_kappa([(True, True)] * 4) is None  # both raters constant: undefined
    assert cohen_kappa([]) is None
