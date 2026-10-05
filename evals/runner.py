"""Run the eval suite N times per case, aggregate pass rates, render a report."""
import re
import unicodedata
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field, replace

from evals.cases import CATEGORIES, EvalCase, Suite
from evals.checks import CheckResult
from evals.evaluate import evaluate
from sales_assistant.assistant import answer
from sales_assistant.catalog import FaqItem, Product
from sales_assistant.client import Responder
from sales_assistant.prompts import load_prompt
from sales_assistant.retriever import build_context

_SECRET = re.compile(r"sk-[A-Za-z0-9_\-*]{6,}")


@dataclass(frozen=True)
class RunResult:
    case_id: str
    category: str
    question: str
    run: int
    text: str = ""
    is_non_answer: bool = False
    checks: tuple[CheckResult, ...] = ()
    retrieved: tuple[str, ...] = ()
    error: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    latency_s: float = 0.0

    @property
    def passed(self) -> bool:
        return not self.error and all(c.passed for c in self.checks)

    @property
    def failed_checks(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed]


def _run_once(case: EvalCase, run: int, suite: Suite, prompt: str, **kwargs) -> RunResult:
    try:
        turn = answer(case.question, case.history, **kwargs)
    except Exception as exc:  # recorded per run; one failed request must not stop the suite
        message = _SECRET.sub("sk-***", f"{type(exc).__name__}: {exc}")
        return RunResult(case.id, case.category, case.question, run, error=message[:300])
    checks = evaluate(case, turn.text, turn.is_non_answer, turn.context, suite=suite, prompt=prompt)
    return RunResult(
        case.id,
        case.category,
        case.question,
        run,
        text=turn.text,
        is_non_answer=turn.is_non_answer,
        checks=tuple(checks),
        retrieved=turn.retrieved,
        input_tokens=turn.reply.input_tokens,
        output_tokens=turn.reply.output_tokens,
        latency_s=turn.reply.latency_s,
    )


def run_suite(
    suite: Suite,
    *,
    responder: Responder,
    model: str,
    prompt_version: str,
    runs: int,
    workers: int,
    products: list[Product],
    faq: list[FaqItem],
) -> list[RunResult]:
    prompt = load_prompt(prompt_version)
    jobs = [(case, run) for case in suite.cases for run in range(1, runs + 1)]
    kwargs = dict(products=products, faq=faq, responder=responder, model=model, prompt_version=prompt_version)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda job: _run_once(job[0], job[1], suite, prompt, **kwargs), jobs))


def rescore(
    results: list[RunResult],
    suite: Suite,
    *,
    products: list[Product],
    faq: list[FaqItem],
    prompt_version: str,
) -> list[RunResult]:
    """Re-apply the current checks to stored replies, without calling the model.

    Lets a fix to a check be measured on the very same generations, so its
    effect is not mixed up with sampling noise.
    """
    cases = {c.id: c for c in suite.cases}
    prompt = load_prompt(prompt_version)
    rescored = []
    for r in results:
        if r.error:
            rescored.append(r)
            continue
        case = cases[r.case_id]
        context = build_context(case.question, products, faq)
        checks = evaluate(case, r.text, r.is_non_answer, context.as_text(), suite=suite, prompt=prompt)
        rescored.append(replace(r, checks=tuple(checks), retrieved=context.skus))
    return rescored


# --- Aggregation --------------------------------------------------------------------

@dataclass
class CaseSummary:
    case_id: str
    category: str
    question: str
    passed_runs: int = 0
    total_runs: int = 0
    errors: int = 0
    retrieved: tuple[str, ...] = ()
    failing: list[RunResult] = field(default_factory=list)


@dataclass
class CategorySummary:
    category: str
    cases: int = 0
    passed_runs: int = 0
    total_runs: int = 0
    stable_pass: int = 0
    flaky: int = 0
    stable_fail: int = 0


@dataclass
class Summary:
    cases: list[CaseSummary]
    categories: list[CategorySummary]
    check_failures: dict[str, tuple[int, tuple[str, ...]]]
    passed_runs: int
    total_runs: int
    errors: int
    input_tokens: int
    output_tokens: int


def summarize(results: list[RunResult]) -> Summary:
    """Pass rates exclude runs that failed with an API error: those say nothing about the model."""
    by_case: dict[str, CaseSummary] = {}
    check_runs: dict[str, int] = defaultdict(int)
    check_cases: dict[str, list[str]] = defaultdict(list)
    for r in results:
        cs = by_case.setdefault(r.case_id, CaseSummary(r.case_id, r.category, r.question))
        if r.error:
            cs.errors += 1
            continue
        cs.total_runs += 1
        cs.retrieved = r.retrieved  # retrieval is deterministic: the same for every run
        if r.passed:
            cs.passed_runs += 1
        else:
            cs.failing.append(r)
            for check in r.failed_checks:
                check_runs[check.name] += 1
                if r.case_id not in check_cases[check.name]:
                    check_cases[check.name].append(r.case_id)

    categories = []
    for category in CATEGORIES:
        members = [c for c in by_case.values() if c.category == category]
        if not members:
            continue
        cat = CategorySummary(category, cases=len(members))
        for c in members:
            cat.passed_runs += c.passed_runs
            cat.total_runs += c.total_runs
            if c.total_runs and c.passed_runs == c.total_runs:
                cat.stable_pass += 1
            elif c.passed_runs:
                cat.flaky += 1
            elif c.total_runs:
                cat.stable_fail += 1
        categories.append(cat)

    valid = [r for r in results if not r.error]
    return Summary(
        cases=list(by_case.values()),
        categories=categories,
        check_failures={k: (check_runs[k], tuple(check_cases[k])) for k in sorted(check_runs, key=lambda k: -check_runs[k])},
        passed_runs=sum(r.passed for r in valid),
        total_runs=len(valid),
        errors=len(results) - len(valid),
        input_tokens=sum(r.input_tokens for r in valid),
        output_tokens=sum(r.output_tokens for r in valid),
    )


# --- Report ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RunMeta:
    model: str
    prompt_version: str
    runs: int
    started_at: str
    duration_s: float


def dump_run(meta: RunMeta, results: list[RunResult]) -> dict:
    return {"meta": asdict(meta), "results": [asdict(r) for r in results]}


def load_run(data: dict) -> tuple[RunMeta, list[RunResult]]:
    results = []
    for row in data["results"]:
        checks = tuple(CheckResult(**c) for c in row.pop("checks"))
        results.append(RunResult(**{**row, "checks": checks, "retrieved": tuple(row["retrieved"])}))
    return RunMeta(**data["meta"]), results


_PUNCT = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-",
                        "\u2026": "...", "\u00a0": " ", "\u2022": "-"})


def _ascii(text: str) -> str:
    """Model replies may contain typographic characters; reports stay plain ASCII."""
    folded = unicodedata.normalize("NFKD", text.translate(_PUNCT))
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return folded.encode("ascii", "backslashreplace").decode("ascii")


def _rate(passed: int, total: int) -> str:
    return f"{100 * passed / total:.1f}% ({passed}/{total})" if total else "n/a"


def _excerpt(text: str, limit: int = 280) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 3] + "..."


def render_report(summary: Summary, meta: RunMeta) -> str:
    lines = [
        f"# Eval report: {meta.model}, prompt {meta.prompt_version}",
        "",
        f"- Model: {meta.model}",
        f"- Prompt: {meta.prompt_version}",
        f"- Runs per case: {meta.runs}",
        f"- Started: {meta.started_at}, took {meta.duration_s:.0f} s",
        f"- Model calls: {summary.total_runs + summary.errors} (API errors: {summary.errors})",
        f"- Tokens: {summary.input_tokens:,} in / {summary.output_tokens:,} out",
        f"- **Overall pass rate: {_rate(summary.passed_runs, summary.total_runs)}**",
        "",
        "A run passes when every check on the reply passes. Stable pass / flaky / stable fail",
        f"classify each case by how many of its {meta.runs} runs passed.",
        "",
        "## By category",
        "",
        "| Category | Cases | Pass rate | Stable pass | Flaky | Stable fail |",
        "|---|---|---|---|---|---|",
    ]
    for c in summary.categories:
        lines.append(
            f"| {c.category} | {c.cases} | {_rate(c.passed_runs, c.total_runs)} | {c.stable_pass} | {c.flaky} | {c.stable_fail} |"
        )

    lines += ["", "## Failed checks", ""]
    if summary.check_failures:
        lines += ["| Check | Failed runs | Cases |", "|---|---|---|"]
        for name, (runs, case_ids) in summary.check_failures.items():
            lines.append(f"| {name} | {runs} | {', '.join(case_ids)} |")
    else:
        lines.append("None.")

    lines += ["", "## Cases with failures", ""]
    failing = [c for c in summary.cases if c.failing or c.errors]
    if not failing:
        lines.append("None.")
    for c in failing:
        retrieved = ", ".join(c.retrieved) if c.retrieved else "none (catalog overview)"
        lines += [
            f"### {c.case_id} ({c.category}): {c.passed_runs}/{c.total_runs}",
            "",
            f"Question: {c.question}",
            f"Retrieved: {retrieved}",
            "",
        ]
        if c.errors:
            lines.append(f"- API errors: {c.errors}")
        for r in c.failing:
            details = "; ".join(f"{k.name}: {k.detail}" if k.detail else k.name for k in r.failed_checks)
            lines.append(f"- Run {r.run}: {details}")
            lines.append(f"  > {_excerpt(r.text)}")
        lines.append("")
    return _ascii("\n".join(lines).rstrip() + "\n")
