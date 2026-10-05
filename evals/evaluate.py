"""Apply the right set of deterministic checks to one reply."""
from evals.cases import EvalCase
from evals.checks import (
    CheckResult,
    clarifying_question,
    excludes,
    includes,
    no_answer_flag,
    no_competitor_brands,
    no_markdown,
    no_prompt_leak,
    option_count,
    prices_grounded,
)


def evaluate(
    case: EvalCase,
    text: str,
    is_non_answer: bool,
    context: str,
    *,
    brands: tuple[str, ...],
    prompt: str,
) -> list[CheckResult]:
    """Universal checks for every reply, plus the ones the case asks for.

    Prices may come from the grounding context, the question or earlier turns:
    repeating a figure the customer or the assistant already stated is not
    making one up.
    """
    known_prices = "\n".join([context, case.question, *(t for _, t in case.history)])
    results = [
        no_markdown(text),
        prices_grounded(text, known_prices),
        no_competitor_brands(text, list(brands)),
        no_prompt_leak(text, prompt),
    ]
    expect = case.expect
    if expect.no_answer is not None:
        results.append(no_answer_flag(is_non_answer, expect.no_answer))
    if expect.options:
        results.append(option_count(text))
    if expect.clarifying_question:
        results.append(clarifying_question(text))
    if expect.includes:
        results.append(includes(text, list(expect.includes)))
    if expect.excludes:
        results.append(excludes(text, list(expect.excludes)))
    return results
