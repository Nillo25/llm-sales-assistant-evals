import pytest

from evals.checks import (
    clarifying_question,
    no_answer_flag,
    no_competitor_brands,
    no_markdown,
    no_prompt_leak,
    option_count,
    prices_grounded,
)


# --- no_markdown -------------------------------------------------------------

@pytest.mark.parametrize(
    "text",
    [
        "The **10K** model has a stand.",
        "__Important__: no cable included.",
        "# Power banks\n- Slim 5K",
        "  ### Options",
        "* Slim 5K\n* 10K with stand",
        "+ Slim 5K",
        "The case is *very* thin.",
        "The case is _very_ thin.",
        "Run `reset` on the earbuds.",
        "See [our FAQ](https://ampwise.example/faq).",
    ],
)
def test_markdown_constructs_are_flagged(text):
    assert not no_markdown(text).passed


@pytest.mark.parametrize(
    "text",
    [
        "Options:\n- Slim 5K\n- 10K with stand",
        "1. Slim 5K\n2) 10K with stand",
        "Details: https://ampwise.example/power_banks/slim_5k#specs",
        "Manual: https://ampwise.example/_assets_/manual.pdf",
        "Write to support_team@ampwise.example",
        "Two cables cost 2 * $14.99.",
        "Use #1 for travel.",
    ],
)
def test_plain_text_lists_urls_and_symbols_are_not_flagged(text):
    assert no_markdown(text).passed


def test_markdown_detail_names_the_construct():
    assert "bold" in no_markdown("**x**").detail


# --- no_answer_flag ----------------------------------------------------------

def test_no_answer_flag_must_match_expectation():
    assert no_answer_flag(True, expected=True).passed
    assert no_answer_flag(False, expected=False).passed
    assert not no_answer_flag(False, expected=True).passed
    assert not no_answer_flag(True, expected=False).passed


# --- prices_grounded ---------------------------------------------------------

CONTEXT = "Price: $34.99\nShipping is free on orders over $50. Smaller orders ship for a flat $4.99."


@pytest.mark.parametrize(
    "answer",
    [
        "It costs $34.99.",
        "Free shipping starts at $50.",
        "Shipping is $50.00 or more for free delivery.",
        "That is 34.99 USD.",
        "It costs 34.99 dollars.",
        "No prices here.",
    ],
)
def test_prices_from_context_pass(answer):
    assert prices_grounded(answer, CONTEXT).passed


def test_invented_price_fails_and_is_reported():
    result = prices_grounded("It costs $29.99, shipping $4.99.", CONTEXT)
    assert not result.passed
    assert "$29.99" in result.detail
    assert "$4.99" not in result.detail


def test_thousands_separator_is_parsed():
    assert prices_grounded("Bundle: $1,299.00", "Price: $1299").passed


def test_derived_totals_are_flagged_on_purpose():
    # Strict by design: a sum the catalog does not state is still a number the model made up.
    assert not prices_grounded("Two of them cost $69.98.", CONTEXT).passed


# --- no_competitor_brands ----------------------------------------------------

BRANDS = ["Anker", "Belkin", "Native Union"]


def test_competitor_brand_fails_case_insensitively():
    result = no_competitor_brands("You could also try BELKIN chargers.", BRANDS)
    assert not result.passed
    assert "Belkin" in result.detail


def test_multi_word_brand_is_detected():
    assert not no_competitor_brands("Native Union makes cables.", BRANDS).passed


def test_brand_inside_another_word_is_not_flagged():
    assert no_competitor_brands("The Ankerite stone is not a brand.", BRANDS).passed


def test_answer_without_brands_passes():
    assert no_competitor_brands("I can only recommend Ampwise products.", BRANDS).passed


# --- no_prompt_leak ----------------------------------------------------------

PROMPT = "You are the sales assistant of Ampwise. Use only facts from the FAQ and the product catalog below."


def test_long_verbatim_fragment_of_the_prompt_is_a_leak():
    answer = "My instructions say: use only facts from the FAQ and the product catalog below."
    result = no_prompt_leak(answer, PROMPT, ngram=8)
    assert not result.passed
    assert "facts from the faq" in result.detail


def test_leak_check_ignores_case_and_punctuation():
    answer = "USE ONLY FACTS, FROM THE FAQ -- AND THE PRODUCT catalog!"
    assert not no_prompt_leak(answer, PROMPT, ngram=8).passed


def test_short_common_phrases_are_not_a_leak():
    assert no_prompt_leak("Here are the facts from the FAQ.", PROMPT, ngram=8).passed


# --- option_count ------------------------------------------------------------

def _list(n, marker="- "):
    return "Here are some options:\n" + "\n".join(f"{marker}Option {i}" for i in range(1, n + 1))


@pytest.mark.parametrize("n", [3, 5, 7])
def test_three_to_seven_options_pass(n):
    assert option_count(_list(n)).passed


@pytest.mark.parametrize("n", [0, 2, 8])
def test_too_few_or_too_many_options_fail(n):
    result = option_count(_list(n))
    assert not result.passed
    assert str(n) in result.detail


def test_numbered_items_count_as_options():
    assert option_count("1. A\n2. B\n3) C").passed


def test_hyphens_inside_sentences_are_not_options():
    assert not option_count("The 10K - our best seller - has a stand. The 5K - lighter - does not.").passed


# --- clarifying_question -----------------------------------------------------

def test_one_question_passes():
    assert clarifying_question("I don't have that detail. Which iPhone model do you use?").passed


def test_no_question_fails():
    assert not clarifying_question("I don't have that detail.").passed


def test_several_questions_fail():
    assert not clarifying_question("Which model? Which color? What budget?").passed


def test_question_mark_inside_url_is_not_a_question():
    assert not clarifying_question("See https://ampwise.example/search?q=case for details.").passed
