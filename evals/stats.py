"""Uncertainty for pass rates measured on a few runs of a sampled model.

Runs of the same case are not independent (one hard case fails in most of its
runs), so intervals for a pass rate resample whole cases, not single runs: a
case bootstrap. Comparisons of two runs on the same cases resample the same
cases on both sides, which removes the case-to-case spread from the difference.

No SciPy: the binomial bound uses bisection, the bootstrap a seeded RNG, so
reports are reproducible.
"""
import math
import random
from collections.abc import Mapping
from dataclasses import dataclass

# (passed runs, total runs) per case
CaseCounts = Mapping[str, tuple[int, int]]

BOOTSTRAP_ITERATIONS = 10_000
CONFIDENCE = 0.95


@dataclass(frozen=True)
class Interval:
    estimate: float
    low: float
    high: float

    def pp(self) -> str:
        """Percentages, for a pass rate: '80.6% [74.0, 86.8]'."""
        return f"{100 * self.estimate:.1f}% [{100 * self.low:.1f}, {100 * self.high:.1f}]"

    def delta_pp(self) -> str:
        """Percentage points, for a difference: '+9.3 pp [+3.9, +14.7]'."""
        return f"{100 * self.estimate:+.1f} pp [{100 * self.low:+.1f}, {100 * self.high:+.1f}]"

    @property
    def excludes_zero(self) -> bool:
        return self.low > 0 or self.high < 0


def wilson(passed: int, total: int, confidence: float = CONFIDENCE) -> Interval:
    """Wilson score interval for one binomial proportion, e.g. one case's runs."""
    if total <= 0:
        raise ValueError("total must be positive")
    z = _z(confidence)
    p = passed / total
    centre = (p + z * z / (2 * total)) / (1 + z * z / total)
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return Interval(p, max(0.0, centre - half), min(1.0, centre + half))


def failure_upper_bound(failures: int, total: int, confidence: float = CONFIDENCE) -> float:
    """One-sided exact (Clopper-Pearson) upper bound on the true failure rate.

    0 failures in 3 runs still allows a failure rate of up to 63% at 95%
    confidence; 0 in 30 allows 9.5%. This is how many runs an attack needs
    before "it never worked" means something.
    """
    if total <= 0:
        raise ValueError("total must be positive")
    if failures >= total:
        return 1.0
    alpha = 1 - confidence
    lo, hi = failures / total, 1.0
    for _ in range(100):  # bisection: P(X <= failures | p) decreases in p
        mid = (lo + hi) / 2
        if _binom_cdf(failures, total, mid) > alpha:
            lo = mid
        else:
            hi = mid
    return hi


def runs_needed(max_failure_rate: float, confidence: float = CONFIDENCE) -> int:
    """Failure-free runs needed before the upper bound drops to max_failure_rate."""
    return math.ceil(math.log(1 - confidence) / math.log(1 - max_failure_rate))


def pooled_rate(counts: CaseCounts) -> float:
    passed = sum(p for p, _ in counts.values())
    total = sum(t for _, t in counts.values())
    return passed / total if total else 0.0


def case_bootstrap(
    counts: CaseCounts, iterations: int = BOOTSTRAP_ITERATIONS, seed: int = 0, confidence: float = CONFIDENCE
) -> Interval:
    """Interval for a pooled pass rate, resampling whole cases."""
    if not counts:
        raise ValueError("no cases")
    cases = list(counts.values())
    rng = random.Random(seed)
    stats = []
    for _ in range(iterations):
        sample = [cases[rng.randrange(len(cases))] for _ in cases]
        total = sum(t for _, t in sample)
        stats.append(sum(p for p, _ in sample) / total if total else 0.0)
    low, high = _percentiles(stats, confidence)
    return Interval(pooled_rate(counts), low, high)


def paired_bootstrap(
    base: CaseCounts,
    cand: CaseCounts,
    iterations: int = BOOTSTRAP_ITERATIONS,
    seed: int = 0,
    confidence: float = CONFIDENCE,
) -> Interval:
    """Interval for cand minus base pass rate on the cases both runs share.

    Each bootstrap sample draws the same cases for both sides, so the
    comparison is not drowned by how much harder some cases are than others.
    """
    shared = sorted(set(base) & set(cand))
    if not shared:
        raise ValueError("no shared cases")
    pairs = [(base[c], cand[c]) for c in shared]

    def diff(sample) -> float:
        bt = sum(b[1] for b, _ in sample)
        ct = sum(c[1] for _, c in sample)
        return sum(c[0] for _, c in sample) / ct - sum(b[0] for b, _ in sample) / bt

    rng = random.Random(seed)
    stats = [diff([pairs[rng.randrange(len(pairs))] for _ in pairs]) for _ in range(iterations)]
    low, high = _percentiles(stats, confidence)
    return Interval(diff(pairs), low, high)


def pass_hat_k(counts: CaseCounts) -> float:
    """pass^k: share of cases that passed every one of their runs (the 'stable pass' share)."""
    return sum(1 for p, t in counts.values() if t and p == t) / len(counts) if counts else 0.0


def pass_at_k(counts: CaseCounts) -> float:
    """pass@k: share of cases that passed at least one of their runs."""
    return sum(1 for p, t in counts.values() if p > 0) / len(counts) if counts else 0.0


def cohen_kappa(pairs: list[tuple[bool, bool]]) -> float | None:
    """Agreement between two raters beyond chance; None when it is undefined (one rater is constant)."""
    if not pairs:
        return None
    n = len(pairs)
    observed = sum(a == b for a, b in pairs) / n
    pa = sum(a for a, _ in pairs) / n
    pb = sum(b for _, b in pairs) / n
    expected = pa * pb + (1 - pa) * (1 - pb)
    return None if expected == 1 else (observed - expected) / (1 - expected)


def _percentiles(values: list[float], confidence: float) -> tuple[float, float]:
    values = sorted(values)
    tail = (1 - confidence) / 2
    lo_i = int(math.floor(tail * (len(values) - 1)))
    hi_i = int(math.ceil((1 - tail) * (len(values) - 1)))
    return values[lo_i], values[hi_i]


def _binom_cdf(k: int, n: int, p: float) -> float:
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k + 1))


def _z(confidence: float) -> float:
    # Two-sided normal quantile by bisection on erf, to avoid a SciPy dependency.
    target = 1 - (1 - confidence) / 2
    lo, hi = 0.0, 10.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if 0.5 * (1 + math.erf(mid / math.sqrt(2))) < target:
            lo = mid
        else:
            hi = mid
    return hi
