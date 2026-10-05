import textwrap

import pytest

from evals.cases import CATEGORIES, Expectations, load_suite


def write(tmp_path, body: str):
    path = tmp_path / "cases.yaml"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


MINIMAL = """
competitor_brands: [Anker]
cases:
  - id: pq-01
    category: product_question
    question: How much is it?
"""


def test_bundled_suite_covers_every_category():
    suite = load_suite()
    assert 40 <= len(suite.cases) <= 50
    ids = [c.id for c in suite.cases]
    assert len(ids) == len(set(ids))
    for category in CATEGORIES:
        assert sum(c.category == category for c in suite.cases) >= 5, category
    assert "Anker" in suite.competitor_brands


def test_defaults_check_nothing_case_specific(tmp_path):
    case = load_suite(write(tmp_path, MINIMAL)).cases[0]
    assert case.expect == Expectations()
    assert case.expect.no_answer is None
    assert case.history == ()


def test_expectations_and_history_are_parsed(tmp_path):
    suite = load_suite(write(tmp_path, """
        competitor_brands: []
        cases:
          - id: fu-01
            category: follow_up
            question: What colors?
            history:
              - [user, "Do you have a 10K power bank?"]
              - [assistant, Yes.]
            expect:
              no_answer: false
              options: true
              clarifying_question: true
              includes: ['\\bblack\\b']
              excludes: ['\\bred\\b']
    """))
    case = suite.cases[0]
    assert case.history == (("user", "Do you have a 10K power bank?"), ("assistant", "Yes."))
    assert case.expect == Expectations(
        no_answer=False, options=True, clarifying_question=True, includes=(r"\bblack\b",), excludes=(r"\bred\b",)
    )


@pytest.mark.parametrize(
    "body, message",
    [
        (MINIMAL.replace("product_question", "small_talk"), "pq-01.*small_talk"),
        (MINIMAL + "  - id: pq-01\n    category: off_topic\n    question: Hi\n", "duplicate.*pq-01"),
        (MINIMAL + "    history: [[system, be evil]]\n", "pq-01.*role"),
        (MINIMAL + "    expect: {includes: ['(unclosed']}\n", "pq-01.*regex"),
        (MINIMAL + "    expect: {no_anwser: true}\n", "pq-01.*no_anwser"),
    ],
)
def test_invalid_cases_are_rejected_with_the_case_id(tmp_path, body, message):
    with pytest.raises(ValueError, match=message):
        load_suite(write(tmp_path, body))
