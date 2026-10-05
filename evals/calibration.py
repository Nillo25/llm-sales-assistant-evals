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
        return CalibrationResult(item.id, metric, expected, s.passed, s.score, s.reason)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(run_one, jobs))


def render_calibration_report(results: list[CalibrationResult], judge_model: str, variant: str) -> str:
    agreeing = sum(r.agrees for r in results)
    lines = [
        f"# Judge calibration: {judge_model} ({variant})",
        "",
        f"- Agreement with human labels: {agreeing}/{len(results)}",
        "- False alarm: the human says pass, the judge fails it. Miss: the human says fail, the judge passes it.",
        "",
        "| Metric | Agreement | False alarms | Misses |",
        "|---|---|---|---|",
    ]
    for metric in ALL_METRICS:
        rows = [r for r in results if r.metric == metric]
        if not rows:
            continue
        false_alarms = sum(1 for r in rows if not r.error and r.expected and not r.passed)
        misses = sum(1 for r in rows if not r.error and not r.expected and r.passed)
        lines.append(f"| {metric} | {sum(r.agrees for r in rows)}/{len(rows)} | {false_alarms} | {misses} |")

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
