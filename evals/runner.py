"""Run the eval suite N times per case, aggregate pass rates, render a report."""
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field, replace

from evals.cases import CATEGORIES, EvalCase, Suite
from evals.checks import CheckResult
from evals.evaluate import evaluate
from evals.stats import case_bootstrap, failure_upper_bound, pass_at_k, pass_hat_k, runs_needed
from evals.text import ascii_fold, excerpt
from sales_assistant.assistant import answer
from sales_assistant.catalog import FaqItem, Product
from sales_assistant.client import Responder
from sales_assistant.prompts import load_prompt
from sales_assistant.retriever import context_for_skus

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
    guard_actions: tuple[str, ...] = ()

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
        guard_actions=turn.guard_actions,
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
    temperature: float | None = None,
    jobs: list[tuple[EvalCase, int]] | None = None,
    guard: bool = False,
) -> list[RunResult]:
    """Run every case `runs` times, or exactly the (case, run number) pairs in `jobs`."""
    prompt = load_prompt(prompt_version)
    if jobs is None:
        jobs = [(case, run) for case in suite.cases for run in range(1, runs + 1)]
    kwargs = dict(
        products=products, faq=faq, responder=responder, model=model, prompt_version=prompt_version,
        temperature=temperature, guard=guard,
    )
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
        context = context_for_skus(r.retrieved, products, faq)
        checks = evaluate(case, r.text, r.is_non_answer, context.as_text(), suite=suite, prompt=prompt)
        rescored.append(replace(r, checks=tuple(checks)))
    return rescored


def adaptive_jobs(
    results: list[RunResult], suite: Suite, *, max_runs: int, categories: tuple[str, ...] = ()
) -> list[tuple[EvalCase, int]]:
    """Extra runs where a few runs say little: flaky cases, and every case in `categories`.

    A case that passed 3/3 can still fail 20% of the time, and an attack that
    failed 0/3 can still work up to 63% of the time (see evals/stats.py). Flaky
    cases and the categories where a single failure matters are topped up to
    max_runs; stable cases elsewhere keep their runs, which keeps the cost down.
    """
    done: dict[str, list[RunResult]] = defaultdict(list)
    for r in results:
        done[r.case_id].append(r)
    jobs = []
    for case in suite.cases:
        runs = done.get(case.id, [])
        valid = [r for r in runs if not r.error]
        flaky = 0 < sum(r.passed for r in valid) < len(valid)
        if not (flaky or case.category in categories):
            continue
        last = max((r.run for r in runs), default=0)
        jobs.extend((case, run) for run in range(last + 1, last + 1 + max_runs - len(runs)))
    return jobs


def apply_guard(
    results: list[RunResult],
    suite: Suite,
    *,
    products: list[Product],
    faq: list[FaqItem],
    prompt_version: str,
) -> tuple[list[RunResult], list[tuple[str, int, tuple[str, ...]]]]:
    """Run the output guard over stored replies and re-check what it lets through.

    The guard is deterministic post-processing of the reply, so replaying it on
    stored replies gives exactly what a live run would have sent for those same
    samples: guarded and unguarded results differ only by the guard, with no
    sampling noise between them. Returns the guarded results and, per changed
    reply, (case id, run, guard actions).
    """
    from sales_assistant.guard import guard_reply

    cases = {c.id: c for c in suite.cases}
    prompt = load_prompt(prompt_version)
    guarded, changes = [], []
    for r in results:
        if r.error:
            guarded.append(r)
            continue
        case = cases[r.case_id]
        context = context_for_skus(r.retrieved, products, faq).as_text()
        g = guard_reply(r.text, system_prompt=prompt, context=context, question=case.question)
        if not g.changed:
            guarded.append(r)
            continue
        changes.append((r.case_id, r.run, g.actions))
        checks = evaluate(case, g.text, r.is_non_answer, context, suite=suite, prompt=prompt)
        guarded.append(replace(r, text=g.text, checks=tuple(checks)))
    return guarded, changes


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


def case_counts(cases: list[CaseSummary]) -> dict[str, tuple[int, int]]:
    return {c.case_id: (c.passed_runs, c.total_runs) for c in cases if c.total_runs}


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
    retrieval: str = "r1"  # runs stored before retrieval was versioned used r1
    temperature: float | None = None  # None: the API default (1.0 for the OpenAI models used here)
    max_runs: int | None = None  # set when flaky and security cases were topped up (adaptive runs)
    guard: bool = False  # replies went through the output guard (sales_assistant.guard)


def dump_run(meta: RunMeta, results: list[RunResult]) -> dict:
    return {"meta": asdict(meta), "results": [asdict(r) for r in results]}


def load_run(data: dict) -> tuple[RunMeta, list[RunResult]]:
    results = []
    for row in data["results"]:
        checks = tuple(CheckResult(**c) for c in row.pop("checks"))
        extra = {"guard_actions": tuple(row["guard_actions"])} if "guard_actions" in row else {}
        results.append(RunResult(**{**row, "checks": checks, "retrieved": tuple(row["retrieved"]), **extra}))
    return RunMeta(**data["meta"]), results


def _rate(passed: int, total: int) -> str:
    return f"{100 * passed / total:.1f}% ({passed}/{total})" if total else "n/a"


ATTACK_CATEGORIES = ("prompt_injection",)


def _runs_line(meta: RunMeta) -> str:
    if meta.max_runs:
        return f"- Runs per case: {meta.runs}, topped up to {meta.max_runs} for flaky and security cases"
    return f"- Runs per case: {meta.runs}"


def _temperature(meta: RunMeta) -> str:
    return "API default" if meta.temperature is None else f"{meta.temperature:g}"


def _category_interval(counts: dict[str, tuple[int, int]]) -> str:
    """Bootstrap interval; when every case passed (or failed) it collapses, so give a one-sided bound instead.

    8 of 8 cases passing every run still leaves room for 31% of such cases failing (95%, one-sided).
    """
    if not counts:
        return "n/a"
    ci = case_bootstrap(counts)
    if ci.low < ci.high or ci.estimate not in (0.0, 1.0):
        return f"[{100 * ci.low:.1f}, {100 * ci.high:.1f}]"
    bound = 100 * failure_upper_bound(0, len(counts))
    return f"case-level >= {100 - bound:.1f}" if ci.estimate == 1 else f"case-level <= {bound:.1f}"


def render_report(summary: Summary, meta: RunMeta) -> str:
    counts = case_counts(summary.cases)
    overall = case_bootstrap(counts) if counts else None
    lines = [
        f"# Eval report: {meta.model}, prompt {meta.prompt_version}",
        "",
        f"- Model: {meta.model}",
        f"- Prompt: {meta.prompt_version}",
        f"- Retrieval: {meta.retrieval}",
        _runs_line(meta),
        f"- Temperature: {_temperature(meta)}",
        f"- Output guard: {'on' if meta.guard else 'off'}",
        f"- Started: {meta.started_at}, took {meta.duration_s:.0f} s",
        f"- Model calls: {summary.total_runs + summary.errors} (API errors: {summary.errors})",
        f"- Tokens: {summary.input_tokens:,} in / {summary.output_tokens:,} out",
        f"- **Overall pass rate: {_rate(summary.passed_runs, summary.total_runs)}**",
    ]
    if overall:
        lines += [
            f"- 95% interval (case bootstrap): [{100 * overall.low:.1f}, {100 * overall.high:.1f}]",
            f"- pass^k (every run passed): {100 * pass_hat_k(counts):.1f}% of cases; "
            f"pass@k (at least one run passed): {100 * pass_at_k(counts):.1f}%",
        ]
    lines += [
        "",
        "A run passes when every check on the reply passes. Stable pass (pass^k) / flaky / stable fail",
        "classify each case by how many of its runs passed. Intervals resample whole cases, because",
        "runs of one case are not independent; with few cases per category they are wide.",
        "",
        "## By category",
        "",
        "| Category | Cases | Pass rate | 95% interval | Stable pass | Flaky | Stable fail |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in summary.categories:
        sub = {k: v for k, v in counts.items() if k in {x.case_id for x in summary.cases if x.category == c.category}}
        interval = _category_interval(sub)
        lines.append(
            f"| {c.category} | {c.cases} | {_rate(c.passed_runs, c.total_runs)} | {interval} "
            f"| {c.stable_pass} | {c.flaky} | {c.stable_fail} |"
        )

    attacks = [c for c in summary.cases if c.category in ATTACK_CATEGORIES and c.total_runs]
    if attacks:
        lines += [
            "",
            "## Attack resistance",
            "",
            "Successful attacks per case, with a one-sided 95% upper bound on how often the attack",
            f"can work. Pushing that bound under 10% takes {runs_needed(0.10)} attack-free runs.",
            "",
            "| Case | Attack worked | Upper bound |",
            "|---|---|---|",
        ]
        for c in attacks:
            failures = c.total_runs - c.passed_runs
            bound = failure_upper_bound(failures, c.total_runs)
            lines.append(f"| {c.case_id} | {failures}/{c.total_runs} | {100 * bound:.0f}% |")

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
            lines.append(f"  > {excerpt(r.text)}")
        lines.append("")
    return ascii_fold("\n".join(lines).rstrip() + "\n")


def below_threshold(summary: Summary, fail_under: float | None) -> bool:
    """Quality gate for CI: True when the overall pass rate is under fail_under (0-1)."""
    if fail_under is None or not summary.total_runs:
        return False
    return summary.passed_runs / summary.total_runs < fail_under
