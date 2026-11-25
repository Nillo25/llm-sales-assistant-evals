"""The eval cases as pytest tests against a live model (one run per case).

Opt-in because it costs money:  pytest -m llm
Model and prompt come from EVAL_MODEL (default claude-haiku-5-5) and EVAL_PROMPT (default v1).
For pass rates over repeated runs use scripts/run_evals.py instead.
"""
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from evals.cases import load_suite
from evals.evaluate import evaluate
from sales_assistant.assistant import answer
from sales_assistant.catalog import load_catalog, load_faq
from sales_assistant.client import responder_for
from sales_assistant.prompts import load_prompt

pytestmark = pytest.mark.llm

SUITE = load_suite()


MODEL = os.environ.get("EVAL_MODEL", "claude-haiku-5-5")


@pytest.fixture(scope="module")
def responder():
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    key = "ANTHROPIC_API_KEY" if MODEL.startswith("claude-") else "OPENAI_API_KEY"
    if not os.environ.get(key):
        pytest.skip(f"{key} is not set")
    return responder_for(MODEL)


@pytest.mark.parametrize("case", SUITE.cases, ids=lambda c: c.id)
def test_case(case, responder):
    prompt_version = os.environ.get("EVAL_PROMPT", "v1")
    turn = answer(
        case.question,
        case.history,
        products=load_catalog(),
        faq=load_faq(),
        responder=responder,
        model=MODEL,
        prompt_version=prompt_version,
    )
    checks = evaluate(
        case, turn.text, turn.is_non_answer, turn.context,
        suite=SUITE, prompt=load_prompt(prompt_version),
    )
    failed = [f"{c.name}: {c.detail}" if c.detail else c.name for c in checks if not c.passed]
    assert not failed, "; ".join(failed) + f"\nReply: {turn.text}"
