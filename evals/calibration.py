"""Meta-evaluation: does the LLM judge agree with human verdicts?

evals/judge_calibration.yaml holds replies (real ones from eval runs, plus a
few constructed failures) with a human pass/fail label per metric. Running
the judge on them shows where it raises false alarms or misses real problems,
before its scores are trusted on the full suite.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import yaml

from evals.cases import Suite
from evals.judge import ALL_METRICS, Scorer, judge_input
from evals.stats import cohen_kappa
from evals.text import ascii_fold, excerpt
from sales_assistant.catalog import FaqItem, Product, load_catalog
from sales_assistant.retriever import context_for_skus

CALIBRATION_PATH = Path(__file__).with_name("judge_calibration.yaml")
_LABELS = {"pass": True, "fail": False}


@dataclass(frozen=True)
class CalibrationItem:
    id: str
    case_id: str
    reply: str
    expected: dict[str, bool]
    retrieved: tuple[str, ...] = ()  # the context the reply was labeled against
    note: str = ""


@dataclass(frozen=True)
class CalibrationResult:
    item_id: str
    metric: str
    expected: bool
    passed: bool | None = None
    score: float | None = None
    reason: str = ""
    error: str = ""
    cost: float = 0.0

    @property
    def agrees(self) -> bool:
        return not self.error and self.passed == self.expected


def load_calibration(
    suite: Suite, path: Path = CALIBRATION_PATH, products: list[Product] | None = None
) -> list[CalibrationItem]:
    """Load and validate the labeled set.

    Each item stores the products that were in the context when it was
    labeled: a label like "this color is invented" only holds for that context.
    """
    case_ids = {c.id for c in suite.cases}
    skus = {p.sku for p in (products if products is not None else load_catalog())}
    items, seen = [], set()
    for row in yaml.safe_load(path.read_text(encoding="utf-8")):
        item_id = row["id"]
        if item_id in seen:
            raise ValueError(f"duplicate calibration id {item_id}")
        seen.add(item_id)
        if row["case"] not in case_ids:
            raise ValueError(f"{item_id}: unknown case {row['case']}")
        expected = {}
        for metric, label in row["expected"].items():
            if metric not in ALL_METRICS:
                raise ValueError(f"{item_id}: unknown metric {metric}")
            if label not in _LABELS:
                raise ValueError(f"{item_id}: label must be pass or fail, got {label}")
            expected[metric] = _LABELS[label]
        if "retrieved" not in row:
            raise ValueError(f"{item_id}: retrieved (the products in the labeled context) is required")
        unknown = [sku for sku in row["retrieved"] if sku not in skus]
        if unknown:
            raise ValueError(f"{item_id}: unknown products in retrieved: {', '.join(unknown)}")
        items.append(
            CalibrationItem(
                item_id, row["case"], row["reply"].strip(), expected, tuple(row["retrieved"]), row.get("note", "")
            )
        )
    return items


def run_calibration(
    items: list[CalibrationItem],
    suite: Suite,
    *,
    products: list[Product],
    faq: list[FaqItem],
    scorer: Scorer,
    workers: int = 4,
) -> list[CalibrationResult]:
    cases = {c.id: c for c in suite.cases}
    jobs = []
    for item in items:
        case = cases[item.case_id]
        ji = judge_input(case, item.reply, context_for_skus(item.retrieved, products, faq))
        jobs.extend((item, metric, expected, ji) for metric, expected in item.expected.items())

    def run_one(job) -> CalibrationResult:
        item, metric, expected, ji = job
        try:
            s = scorer(metric, ji)
        except Exception as exc:
            return CalibrationResult(item.id, metric, expected, error=f"{type(exc).__name__}: {exc}"[:300])
        return CalibrationResult(item.id, metric, expected, s.passed, s.score, s.reason, cost=s.cost)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(run_one, jobs))


def kappa(results: list[CalibrationResult]) -> float | None:
    """Cohen's kappa between the judge and the human labels; errors are left out."""
    return cohen_kappa([(r.expected, bool(r.passed)) for r in results if not r.error])


def _kappa_text(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def flips(repeats: list[list[CalibrationResult]]) -> list[tuple[str, str, list[bool | None]]]:
    """(item, metric, verdict per repeat) wherever the judge changed its verdict between repeats."""
    by_key: dict[tuple[str, str], list[bool | None]] = {}
    for results in repeats:
        for r in results:
            by_key.setdefault((r.item_id, r.metric), []).append(None if r.error else r.passed)
    return [(i, m, v) for (i, m), v in by_key.items() if len(set(v)) > 1]


def render_calibration_report(
    results: list[CalibrationResult],
    judge_model: str,
    variant: str,
    repeats: list[list[CalibrationResult]] | None = None,
) -> str:
    """results is the first repeat; repeats, when given, holds all of them (results included)."""
    agreeing = sum(r.agrees for r in results)
    lines = [
        f"# Judge calibration: {judge_model} ({variant})",
        "",
        f"- Agreement with human labels: {agreeing}/{len(results)}, Cohen's kappa {_kappa_text(kappa(results))}",
        "- False alarm: the human says pass, the judge fails it. Miss: the human says fail, the judge passes it.",
        "- Kappa corrects agreement for chance: 1 is perfect, 0 is no better than guessing from the base rate.",
        f"- Judge cost: ${sum(r.cost for rs in (repeats or [results]) for r in rs):.2f}"
        + (f" for {len(repeats)} runs" if repeats and len(repeats) > 1 else ""),
        "",
        "| Metric | Agreement | Kappa | False alarms | Misses |",
        "|---|---|---|---|---|",
    ]
    for metric in ALL_METRICS:
        rows = [r for r in results if r.metric == metric]
        if not rows:
            continue
        false_alarms = sum(1 for r in rows if not r.error and r.expected and not r.passed)
        misses = sum(1 for r in rows if not r.error and not r.expected and r.passed)
        lines.append(
            f"| {metric} | {sum(r.agrees for r in rows)}/{len(rows)} | {_kappa_text(kappa(rows))} "
            f"| {false_alarms} | {misses} |"
        )

    if repeats and len(repeats) > 1:
        changed = flips(repeats)
        lines += [
            "",
            f"## Repeatability ({len(repeats)} runs of the same judge on the same labels)",
            "",
            "A judge is a sampled model too: the same reply can get a different verdict on another run.",
            "",
            "| Run | Agreement | Kappa |",
            "|---|---|---|",
        ]
        for n, rep_results in enumerate(repeats, 1):
            lines.append(
                f"| {n} | {sum(r.agrees for r in rep_results)}/{len(rep_results)} | {_kappa_text(kappa(rep_results))} |"
            )
        lines += ["", f"Verdicts that changed between runs: {len(changed)} of {len(results)}.", ""]
        for item_id, metric, verdicts in changed:
            shown = ", ".join("error" if v is None else ("pass" if v else "fail") for v in verdicts)
            lines.append(f"- {item_id} {metric}: {shown}")

    lines += ["", "## Disagreements", ""]
    disagreements = [r for r in results if not r.agrees]
    if not disagreements:
        lines.append("None.")
    for r in disagreements:
        expected = "pass" if r.expected else "fail"
        if r.error:
            lines.append(f"- {r.item_id} {r.metric}: error: {r.error}")
            continue
        verdict = "passed" if r.passed else "failed"
        lines.append(f"- {r.item_id} {r.metric}: expected {expected}, judge {verdict} ({r.score:.2f})")
        lines.append(f"  > {excerpt(r.reason, 400)}")
    return ascii_fold("\n".join(lines).rstrip() + "\n")
