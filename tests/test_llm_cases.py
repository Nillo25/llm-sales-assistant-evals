"""The eval cases as pytest tests against a live model (one run per case).

Opt-in because it costs money:  pytest -m llm
Model and prompt come from EVAL_MODEL (default gpt-4.1-mini) and EVAL_PROMPT (default v1).
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
from sales_assistant.client import OpenAIResponder
from sales_assistant.prompts import load_prompt

pytestmark = pytest.mark.llm

SUITE = load_suite()


@pytest.fixture(scope="module")
def responder():
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY is not set")
    return OpenAIResponder()


@pytest.mark.parametrize("case", SUITE.cases, ids=lambda c: c.id)
def test_case(case, responder):
    prompt_version = os.environ.get("EVAL_PROMPT", "v1")
    turn = answer(
        case.question,
        case.history,
        products=load_catalog(),
        faq=load_faq(),
        responder=responder,
        model=os.environ.get("EVAL_MODEL", "gpt-4.1-mini"),
        prompt_version=prompt_version,
    )
    checks = evaluate(
        case, turn.text, turn.is_non_answer, turn.context,
        brands=SUITE.competitor_brands, prompt=load_prompt(prompt_version),
    )
    failed = [f"{c.name}: {c.detail}" if c.detail else c.name for c in checks if not c.passed]
    assert not failed, "; ".join(failed) + f"\nReply: {turn.text}"
