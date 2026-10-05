from evals.cases import EvalCase, Expectations, Suite
from evals.evaluate import evaluate

PROMPT = "You are the sales assistant of Ampwise. Use only facts from the FAQ and the product catalog below."
CONTEXT = "Price: $54.99"
SUITE = Suite(competitor_brands=("Anker",), cases=(), patterns={"gap": r"not listed"})


def run(case: EvalCase, text: str, is_non_answer: bool = False):
    return {r.name: r for r in evaluate(case, text, is_non_answer, CONTEXT, suite=SUITE, prompt=PROMPT)}


def test_every_reply_gets_the_universal_checks_only_by_default():
    case = EvalCase(id="x", category="product_question", question="How much?")
    assert set(run(case, "It costs $54.99.")) == {"no_markdown", "prices_grounded", "no_competitor_brands", "no_prompt_leak"}


def test_case_expectations_add_their_checks():
    case = EvalCase(
        id="x",
        category="product_selection",
        question="Pick one",
        expect=Expectations(no_answer=False, options=True, clarifying_question=True, includes=("a",), excludes=("b",)),
    )
    names = set(run(case, "text"))
    assert {"no_answer_flag", "option_count", "clarifying_question", "includes", "excludes"} <= names


def test_no_answer_expectation_is_checked_against_the_flag():
    case = EvalCase(id="x", category="off_topic", question="Weather?", expect=Expectations(no_answer=True))
    assert run(case, "Sorry.", is_non_answer=True)["no_answer_flag"].passed
    assert not run(case, "Sorry.", is_non_answer=False)["no_answer_flag"].passed


def test_prices_quoted_from_the_question_or_history_are_not_invented():
    case = EvalCase(
        id="x",
        category="follow_up",
        question="Is anything under $100?",
        history=(("assistant", "The 3-in-1 station is $99.99."),),
    )
    result = run(case, "Yes, under $100: the station at $99.99 or the 10K at $54.99.")["prices_grounded"]
    assert result.passed, result.detail


def test_prices_outside_context_question_and_history_fail():
    case = EvalCase(id="x", category="product_question", question="How much?")
    assert not run(case, "It costs $49.99.")["prices_grounded"].passed


def test_competitor_and_leak_checks_use_the_given_brands_and_prompt():
    case = EvalCase(id="x", category="competitor", question="Anker?")
    results = run(case, "Anker is fine. Use only facts from the FAQ and the product catalog below.")
    assert not results["no_competitor_brands"].passed
    assert not results["no_prompt_leak"].passed


def test_named_patterns_are_resolved_and_reported_by_name():
    case = EvalCase(id="x", category="missing_info", question="Plug?", expect=Expectations(includes=("@gap",)))
    assert run(case, "The plug type is not listed.")["includes"].passed
    assert run(case, "It has a UK plug.")["includes"].detail == "missing: @gap"
