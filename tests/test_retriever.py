from sales_assistant.catalog import load_catalog, load_faq, render_faq, render_overview, render_product
from sales_assistant.retriever import build_context, retrieve

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
    faq_context, catalog_context = build_context("Do you have a 10K power bank?", CATALOG, FAQ)
    assert faq_context == render_faq(FAQ)
    by_sku = {p.sku: p for p in CATALOG}
    assert catalog_context.startswith(render_product(by_sku["AW-PB-10M"]))


def test_context_falls_back_to_overview_when_nothing_matches():
    _, catalog_context = build_context("Hi there!", CATALOG, FAQ)
    assert catalog_context == render_overview(CATALOG)
