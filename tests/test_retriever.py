from sales_assistant.catalog import load_catalog, load_faq, render_faq, render_overview, render_product
from sales_assistant.retriever import build_context, context_for_skus, retrieve

CATALOG = load_catalog()
FAQ = load_faq()


def skus(products):
    return [p.sku for p in products]


def test_specific_product_ranks_first():
    assert skus(retrieve("Do you have a 10K power bank?", CATALOG))[0] == "AW-PB-10M"


def test_category_query_returns_that_category_first():
    top = retrieve("I need a USB-C cable", CATALOG, k=3)
    assert {p.category for p in top} == {"Cables"}


def test_plural_words_match_singular_names():
    top = retrieve("Show me your chargers", CATALOG, k=3)
    assert all("Charger" in p.name for p in top)


def test_brand_name_alone_does_not_match_everything():
    # Every product name contains the brand, so it carries no signal.
    assert retrieve("Tell me about Ampwise", CATALOG) == []


def test_unrelated_question_retrieves_nothing():
    assert retrieve("What's the weather in Paris tomorrow?", CATALOG) == []


def test_k_limits_the_number_of_results():
    assert len(retrieve("power bank", CATALOG, k=2)) == 2


def test_context_holds_full_faq_and_matching_products():
    context = build_context("Do you have a 10K power bank?", CATALOG, FAQ)
    assert context.faq == render_faq(FAQ)
    by_sku = {p.sku: p for p in CATALOG}
    assert context.catalog.startswith(render_product(by_sku["AW-PB-10M"]))
    assert context.skus[0] == "AW-PB-10M"


def test_context_falls_back_to_overview_when_nothing_matches():
    context = build_context("Hi there!", CATALOG, FAQ)
    assert context.catalog == render_overview(CATALOG)
    assert context.skus == ()


def test_context_can_be_rebuilt_from_stored_skus():
    # Rescoring and judging old runs must see the context the model saw, not today's retrieval.
    for question in ("Do you have a 10K power bank?", "Hi there!"):
        original = build_context(question, CATALOG, FAQ)
        assert context_for_skus(original.skus, CATALOG, FAQ) == original


def test_unknown_stored_sku_is_an_error():
    import pytest

    with pytest.raises(KeyError, match="AW-NOPE"):
        context_for_skus(("AW-NOPE",), CATALOG, FAQ)


# --- r2: word forms and dialog history ------------------------------------------

HISTORY_10K = (
    ("user", "Do you have a 10K power bank?"),
    ("assistant", "Yes, the Ampwise 10K Magnetic Power Bank with Stand, for $54.99."),
)


def test_word_forms_match_each_other():
    # ps-04: "commutes" never reached the earbuds described "for commuting".
    assert "AW-EB-PRO" in skus(retrieve("A gift for someone who commutes by train", CATALOG))
    # ps-h1: "wirelessly" never reached the wireless charging pad.
    assert "AW-WP-15" in skus(retrieve("I want to charge my phone wirelessly on my desk", CATALOG))


def test_follow_up_finds_the_product_from_the_dialog():
    # fu-01: "What colors does it come in?" alone retrieves nothing.
    assert skus(retrieve("What colors does it come in?", CATALOG, history=HISTORY_10K))[0] == "AW-PB-10M"


def test_the_current_question_outweighs_the_history():
    top = skus(retrieve("And the clear case for iPhone 16?", CATALOG, history=HISTORY_10K))
    assert top[0] == "AW-CS-CLR-16"


def test_only_the_last_two_turns_count():
    old = (("user", "Tell me about the AirLite earbuds."), ("assistant", "They cost $59.99.")) + HISTORY_10K
    assert "AW-EB-AIR" not in skus(retrieve("What colors does it come in?", CATALOG, history=old))


def test_build_context_passes_the_history_through():
    context = build_context("What colors does it come in?", CATALOG, FAQ, history=HISTORY_10K)
    assert context.skus[0] == "AW-PB-10M"
    assert "Colors: Black, Blue" in context.catalog


def test_retrieval_version_is_exposed_for_reports():
    from sales_assistant.retriever import RETRIEVAL_VERSION

    assert RETRIEVAL_VERSION == "r2"
