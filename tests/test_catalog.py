from decimal import Decimal

from sales_assistant.catalog import (
    FaqItem,
    Product,
    load_catalog,
    load_faq,
    render_faq,
    render_overview,
    render_product,
)

CASE = Product(
    sku="AW-TEST-1",
    name="Ampwise Test Case",
    category="Cases",
    price=Decimal("29.99"),
    colors=("Clear", "Black"),
    specs=(("Material", "Polycarbonate"), ("Drop protection", "2 m")),
    description="A test case.",
)


def test_bundled_catalog_loads_with_unique_skus_and_positive_prices():
    products = load_catalog()
    assert len(products) >= 12
    skus = [p.sku for p in products]
    assert len(skus) == len(set(skus))
    assert all(p.price > 0 for p in products)
    assert all(p.name and p.category and p.description for p in products)


def test_bundled_faq_loads():
    faq = load_faq()
    assert len(faq) >= 6
    assert all(item.question.endswith("?") and item.answer for item in faq)


def test_product_renders_every_fact_the_model_may_use():
    text = render_product(CASE)
    assert text.splitlines()[0] == "[AW-TEST-1] Ampwise Test Case"
    assert "Category: Cases" in text
    assert "Price: $29.99" in text
    assert "Colors: Clear, Black" in text
    assert "- Material: Polycarbonate" in text
    assert "- Drop protection: 2 m" in text
    assert "A test case." in text


def test_whole_dollar_prices_keep_cents():
    product = Product(**{**CASE.__dict__, "price": Decimal("20")})
    assert "Price: $20.00" in render_product(product)


def test_faq_renders_as_question_answer_blocks():
    faq = [FaqItem("Shipping?", "3-6 days."), FaqItem("Returns?", "30 days.")]
    assert render_faq(faq) == "Q: Shipping?\nA: 3-6 days.\n\nQ: Returns?\nA: 30 days."


def test_overview_lists_names_by_category_without_prices():
    other = Product(**{**CASE.__dict__, "sku": "AW-TEST-2", "name": "Ampwise Test Cable", "category": "Cables"})
    text = render_overview([CASE, other])
    assert "Cases:\n- Ampwise Test Case" in text
    assert "Cables:\n- Ampwise Test Cable" in text
    assert "$" not in text


def test_yes_no_spec_values_stay_human_readable():
    # YAML 1.1 parses bare Yes/No as booleans; the model must see the original words.
    specs = {p.sku: dict(p.specs) for p in load_catalog()}
    assert specs["AW-CS-CLR-16"]["Magnetic ring"] == "Yes"
    assert specs["AW-PB-20C"]["Wireless charging"] == "No"
    rendered = "\n".join(render_product(p) for p in load_catalog())
    assert "True" not in rendered and "False" not in rendered
