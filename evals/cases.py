"""Eval cases: loading and validation of evals/cases.yaml."""
import re
from dataclasses import dataclass, field, fields, replace
from pathlib import Path

import yaml

CASES_PATH = Path(__file__).with_name("cases.yaml")

# dev cases are used to find and fix problems; holdout cases are kept apart and only
# measure the result, so a prompt tuned on dev cannot overfit them.
SPLITS = ("dev", "holdout")

CATEGORIES = (
    "product_question",
    "product_selection",
    "missing_info",
    "off_topic",
    "competitor",
    "prompt_injection",
    "follow_up",
)


@dataclass(frozen=True)
class Expectations:
    """Case-specific expectations on top of the checks every reply gets.

    no_answer: whether the NO_ANSWER marker is expected; None means "either is fine".
    """

    no_answer: bool | None = None
    options: bool = False
    clarifying_question: bool = False
    includes: tuple[str, ...] = ()
    excludes: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvalCase:
    id: str
    category: str
    question: str
    history: tuple[tuple[str, str], ...] = ()
    expect: Expectations = Expectations()
    note: str = ""
    split: str = "dev"


@dataclass(frozen=True)
class Suite:
    competitor_brands: tuple[str, ...]
    cases: tuple[EvalCase, ...]
    patterns: dict[str, str] = field(default_factory=dict)

    def select(self, spec: str | None) -> "Suite":
        """Cases matching any comma-separated case id, category or split; all cases for None."""
        if not spec:
            return self
        wanted = {s.strip() for s in spec.split(",") if s.strip()}
        cases = tuple(c for c in self.cases if wanted & {c.id, c.category, c.split})
        if not cases:
            raise ValueError(f"No cases match {spec!r}")
        return replace(self, cases=cases)

    def resolve(self, refs: tuple[str, ...]) -> dict[str, str]:
        """Map each include/exclude entry to its regex: "@name" refers to a shared pattern."""
        return {ref: self.patterns[ref[1:]] if ref.startswith("@") else ref for ref in refs}


_EXPECT_KEYS = {f.name for f in fields(Expectations)}


def _parse_case(row: dict, patterns: dict[str, str]) -> EvalCase:
    case_id = row.get("id", "?")

    def fail(problem: str) -> ValueError:
        return ValueError(f"case {case_id}: {problem}")

    if row.get("category") not in CATEGORIES:
        raise fail(f"unknown category {row.get('category')!r}")
    if row.get("split", "dev") not in SPLITS:
        raise fail(f"split must be one of {', '.join(SPLITS)}, got {row.get('split')!r}")

    history = []
    for role, text in row.get("history", []):
        if role not in ("user", "assistant"):
            raise fail(f"history role must be user or assistant, got {role!r}")
        history.append((role, text))

    raw_expect = row.get("expect", {})
    unknown = set(raw_expect) - _EXPECT_KEYS
    if unknown:
        raise fail(f"unknown expect keys: {', '.join(sorted(unknown))}")
    expect = Expectations(
        **{k: tuple(v) if k in ("includes", "excludes") else v for k, v in raw_expect.items()}
    )
    for ref in expect.includes + expect.excludes:
        if ref.startswith("@") and ref[1:] not in patterns:
            raise fail(f"unknown named pattern {ref}")
        pattern = patterns[ref[1:]] if ref.startswith("@") else ref
        try:
            re.compile(pattern)
        except re.error as exc:
            raise fail(f"bad regex {pattern!r}: {exc}") from None

    return EvalCase(
        id=case_id,
        category=row["category"],
        question=row["question"],
        history=tuple(history),
        expect=expect,
        note=row.get("note", ""),
        split=row.get("split", "dev"),
    )


def load_suite(path: Path = CASES_PATH) -> Suite:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    patterns = dict(data.get("patterns") or {})
    cases = [_parse_case(row, patterns) for row in data["cases"]]
    seen = set()
    for case in cases:
        if case.id in seen:
            raise ValueError(f"duplicate case id {case.id}")
        seen.add(case.id)
    return Suite(competitor_brands=tuple(data.get("competitor_brands", ())), cases=tuple(cases), patterns=patterns)
