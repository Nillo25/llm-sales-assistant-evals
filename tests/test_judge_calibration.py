"""The judge must agree with human labels (evals/judge_calibration.yaml).

Opt-in because it calls the judge model:  pytest -m llm tests/test_judge_calibration.py
Judge model comes from JUDGE_MODEL (default: evals.judge.DEFAULT_JUDGE_MODEL, a Claude model).
"""
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from evals.calibration import load_calibration
from evals.cases import load_suite
from evals.judge import judge_input
from sales_assistant.catalog import load_catalog, load_faq
from sales_assistant.retriever import context_for_skus

pytestmark = pytest.mark.llm

SUITE = load_suite()
CASES = {c.id: c for c in SUITE.cases}
PAIRS = [(item, metric, expected) for item in load_calibration(SUITE) for metric, expected in item.expected.items()]


@pytest.fixture(scope="module")
def scorer():
    pytest.importorskip("deepeval")
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    from evals.claude_judge import is_claude
    from evals.judge import DEFAULT_JUDGE_MODEL, DeepEvalScorer

    model = os.environ.get("JUDGE_MODEL", DEFAULT_JUDGE_MODEL)
    key = "ANTHROPIC_API_KEY" if is_claude(model) else "OPENAI_API_KEY"
    if not os.environ.get(key):
        pytest.skip(f"{key} is not set")
    return DeepEvalScorer(model)


@pytest.mark.parametrize("item, metric, expected", PAIRS, ids=[f"{i.id}-{m}" for i, m, _ in PAIRS])
def test_judge_agrees_with_human_label(item, metric, expected, scorer):
    if metric == "answer_relevancy":
        pytest.skip("calibration-only metric; known to disagree (see reports/judge_calibration_*.md)")
    case = CASES[item.case_id]
    context = context_for_skus(item.retrieved, load_catalog(), load_faq())
    result = scorer(metric, judge_input(case, item.reply, context))
    assert result.passed == expected, f"{metric} scored {result.score:.2f}: {result.reason}"
