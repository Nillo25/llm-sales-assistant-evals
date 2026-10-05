"""Compare two eval runs: a baseline and a candidate (another model or prompt)."""
from collections import Counter
from dataclasses import dataclass

from evals.cases import CATEGORIES
from evals.runner import RunMeta, RunResult
from evals.text import ascii_fold


@dataclass(frozen=True)
class CategoryDelta:
    category: str
    base_passed: int
    base_total: int
    cand_passed: int
    cand_total: int


@dataclass(frozen=True)
class CheckDelta:
    name: str
    base_failed: int
    cand_failed: int


@dataclass(frozen=True)
class CaseChange:
    case_id: str
    category: str
    before: tuple[int, int]  # (passed, total)
    after: tuple[int, int]

    @property
    def kind(self) -> str:
        """fixed / regressed are clear moves; anything else may be run-to-run noise."""
        before = self.before[0] / self.before[1]
        after = self.after[0] / self.after[1]
        if before <= 1 / 3 and after == 1:
            return "fixed"
        if before == 1 and after <= 1 / 3:
            return "regressed"
        return "changed"


@dataclass(frozen=True)
class Comparison:
    base_passed: int
    base_total: int
    cand_passed: int
    cand_total: int
    categories: list[CategoryDelta]
    checks: list[CheckDelta]
    changes: list[CaseChange]


def _per_case(results: list[RunResult]) -> dict[str, tuple[str, int, int]]:
    out: dict[str, tuple[str, int, int]] = {}
    for r in results:
        if r.error:
            continue
        category, passed, total = out.get(r.case_id, (r.category, 0, 0))
        out[r.case_id] = (category, passed + r.passed, total + 1)
    return out


def _failed_checks(results: list[RunResult]) -> Counter:
    return Counter(c.name for r in results if not r.error for c in r.failed_checks)


def compare(base: list[RunResult], cand: list[RunResult]) -> Comparison:
    b, c = _per_case(base), _per_case(cand)
    categories = []
    for category in CATEGORIES:
        bs = [v for v in b.values() if v[0] == category]
        cs = [v for v in c.values() if v[0] == category]
        if bs or cs:
            categories.append(CategoryDelta(
                category, sum(v[1] for v in bs), sum(v[2] for v in bs), sum(v[1] for v in cs), sum(v[2] for v in cs)
            ))
    bf, cf = _failed_checks(base), _failed_checks(cand)
    checks = [CheckDelta(n, bf[n], cf[n]) for n in sorted(bf | cf, key=lambda n: -(bf[n] + cf[n]))]
    changes = [
        CaseChange(case_id, b[case_id][0], b[case_id][1:], c[case_id][1:])
        for case_id in b
        if case_id in c and b[case_id][1] / b[case_id][2] != c[case_id][1] / c[case_id][2]
    ]
    return Comparison(
        base_passed=sum(v[1] for v in b.values()),
        base_total=sum(v[2] for v in b.values()),
        cand_passed=sum(v[1] for v in c.values()),
        cand_total=sum(v[2] for v in c.values()),
        categories=categories,
        checks=checks,
        changes=changes,
    )


def _rate(passed: int, total: int) -> str:
    return f"{100 * passed / total:.1f}% ({passed}/{total})" if total else "n/a"


def _delta(bp: int, bt: int, cp: int, ct: int) -> str:
    if not bt or not ct:
        return "n/a"
    return f"{100 * (cp / ct - bp / bt):+.1f} pp"


def render_comparison(cmp: Comparison, base: RunMeta, cand: RunMeta) -> str:
    title_a, title_b = f"{base.model} / {base.prompt_version}", f"{cand.model} / {cand.prompt_version}"
    lines = [
        f"# Comparison: {title_a} vs {title_b}",
        "",
        "| | Baseline | Candidate | Delta |",
        "|---|---|---|---|",
        f"| Model | {base.model} | {cand.model} | |",
        f"| Prompt | {base.prompt_version} | {cand.prompt_version} | |",
        f"| Runs per case | {base.runs} | {cand.runs} | |",
        f"| Started | {base.started_at} | {cand.started_at} | |",
        f"| Overall pass rate | {_rate(cmp.base_passed, cmp.base_total)} | {_rate(cmp.cand_passed, cmp.cand_total)} "
        f"| {_delta(cmp.base_passed, cmp.base_total, cmp.cand_passed, cmp.cand_total)} |",
        "",
        "## By category",
        "",
        "| Category | Baseline | Candidate | Delta |",
        "|---|---|---|---|",
    ]
    for d in cmp.categories:
        lines.append(
            f"| {d.category} | {_rate(d.base_passed, d.base_total)} | {_rate(d.cand_passed, d.cand_total)} "
            f"| {_delta(d.base_passed, d.base_total, d.cand_passed, d.cand_total)} |"
        )
    lines += ["", "## Failed runs by check", "", "| Check | Baseline | Candidate |", "|---|---|---|"]
    lines += [f"| {d.name} | {d.base_failed} | {d.cand_failed} |" for d in cmp.checks] or ["| none | 0 | 0 |"]

    lines += [
        "",
        "## Case changes",
        "",
        "Fixed: failing in most runs before, passing every run now. Regressed: the opposite.",
        "Other changes are partial moves that can be run-to-run noise at this number of runs.",
    ]
    for kind, title in (("fixed", "Fixed"), ("regressed", "Regressed"), ("changed", "Other changes")):
        group = [c for c in cmp.changes if c.kind == kind]
        lines += ["", f"### {title}", ""]
        lines += [
            f"- {c.case_id} ({c.category}): {c.before[0]}/{c.before[1]} -> {c.after[0]}/{c.after[1]}" for c in group
        ] or ["None."]
    return ascii_fold("\n".join(lines).rstrip() + "\n")
