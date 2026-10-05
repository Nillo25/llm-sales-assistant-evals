"""Lexical retrieval of catalog entries for a customer question.

Deliberately simple and deterministic: the evals target the model's behavior,
so the context it receives must be reproducible run to run. Like the
production assistant, it looks only at the latest customer message.
"""
import re
from dataclasses import dataclass

from sales_assistant.catalog import FaqItem, Product, render_faq, render_overview, render_product

# "ampwise" is in every product name, so it carries no signal.
_STOPWORDS = frozenset(
    """
    a about all am an and any are as at be best buy by can could do does for from get good
    has have hello hi how i if in is it its me my need of on or our please s show some t tell
    than that the there this to want we what whats which will with would you your ampwise
    """.split()
)
_NAME_WEIGHT, _CATEGORY_WEIGHT, _OTHER_WEIGHT = 3, 2, 1


def _stem(token: str) -> str:
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {_stem(w) for w in words if len(w) > 1 and w not in _STOPWORDS}


def _score(query: set[str], product: Product) -> int:
    name = _tokens(product.name)
    category = _tokens(product.category)
    other = _tokens(" ".join([product.description, *product.colors, *(f"{k} {v}" for k, v in product.specs)]))
    score = 0
    for token in query:
        if token in name:
            score += _NAME_WEIGHT
        elif token in category:
            score += _CATEGORY_WEIGHT
        elif token in other:
            score += _OTHER_WEIGHT
    return score


def retrieve(question: str, products: list[Product], k: int = 5) -> list[Product]:
    """Top-k products by keyword overlap; ties keep catalog order."""
    query = _tokens(question)
    scored = [(_score(query, p), i, p) for i, p in enumerate(products)]
    ranked = sorted((s for s in scored if s[0] > 0), key=lambda s: (-s[0], s[1]))
    return [p for _, _, p in ranked[:k]]


@dataclass(frozen=True)
class Context:
    faq: str
    catalog: str
    skus: tuple[str, ...]  # retrieved products; empty when the overview was used


def build_context(question: str, products: list[Product], faq: list[FaqItem], k: int = 5) -> Context:
    """Grounding context for the payload.

    The whole FAQ is always included. The catalog part holds the matching
    products in full, or a name-only overview when nothing matches.
    """
    hits = retrieve(question, products, k=k)
    catalog = "\n\n".join(render_product(p) for p in hits) if hits else render_overview(products)
    return Context(faq=render_faq(faq), catalog=catalog, skus=tuple(p.sku for p in hits))
