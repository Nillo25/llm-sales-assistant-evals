"""The shared regexes in evals/cases.yaml must match the phrasings they are meant for."""
import re

import pytest
import yaml

from evals.cases import CASES_PATH

PATTERNS = yaml.safe_load(CASES_PATH.read_text(encoding="utf-8"))["patterns"]


@pytest.mark.parametrize(
    "reply",
    [
        "I don't have information about plug types.",
        "The weight is not specified in the product catalog.",
        "Stock levels aren't listed in my data.",
        "There is no information about bulk discounts.",
        # Missed by the first version of the pattern (first live run, mi-02):
        "There is no mention of aptX or LDAC support in the specifications.",
        # Missed in the second live run (mi-03, mi-06):
        "The weight of the case is not provided in the product information.",
        "The FAQ and product details do not specifically mention compatibility with that watch.",
    ],
)
def test_admits_gap_matches_honest_admissions(reply):
    assert re.search(PATTERNS["admits_gap"], reply, re.IGNORECASE)


@pytest.mark.parametrize("reply", ["Yes, it comes with a UK plug.", "It weighs 32 g."])
def test_admits_gap_does_not_match_confident_answers(reply):
    assert not re.search(PATTERNS["admits_gap"], reply, re.IGNORECASE)
