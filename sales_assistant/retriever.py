"""Lexical retrieval of catalog entries for a customer question.

Deliberately simple and deterministic: the evals target the model's behavior,
so the context it receives must be reproducible run to run.

r1 (baseline) mirrored the production assistant: the latest message only, and
plurals as the only word forms. r2 fixes what the evals found: follow-ups such
as "what colors does it come in?" also search the last two dialog turns, at
half the weight of the question, and common word forms match (commutes /
commuting, wirelessly / wireless).
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
_QUESTION_WEIGHT, _HISTORY_WEIGHT = 2, 1
_HISTORY_TURNS = 2
_SUFFIXES = ("ingly", "edly", "ing", "ed", "ly", "es", "s")

RETRIEVAL_VERSION = "r2"


def _stem(token: str) -> str:
    """A light suffix stripper: commutes, commuting and commute all become "commut"."""
    for suffix in _SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            if suffix == "s" and token.endswith("ss"):
                break
            token = token[: -len(suffix)]
            break
    if token.endswith("e") and len(token) > 3:
        token = token[:-1]
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


def retrieve(
    question: str,
    products: list[Product],
    k: int = 5,
    history: tuple[tuple[str, str], ...] = (),
) -> list[Product]:
    """Top-k products by keyword overlap; ties keep catalog order.

    The last dialog turns count at half the weight of the question, so a
    follow-up finds the product under discussion but a new topic still wins.
    """
    query = _tokens(question)
    recent = _tokens(" ".join(text for _, text in history[-_HISTORY_TURNS:]))
    scored = [
        (_QUESTION_WEIGHT * _score(query, p) + _HISTORY_WEIGHT * _score(recent, p), i, p)
        for i, p in enumerate(products)
    ]
    ranked = sorted((s for s in scored if s[0] > 0), key=lambda s: (-s[0], s[1]))
    return [p for _, _, p in ranked[:k]]


@dataclass(frozen=True)
class Context:
    faq: str
    catalog: str
    skus: tuple[str, ...]  # retrieved products; empty when the overview was used

    def as_text(self) -> str:
        return f"FAQ:\n{self.faq}\n\nProduct catalog:\n{self.catalog}"


def build_context(
    question: str,
    products: list[Product],
    faq: list[FaqItem],
    k: int = 5,
    history: tuple[tuple[str, str], ...] = (),
) -> Context:
    """Grounding context for the payload.

    The whole FAQ is always included. The catalog part holds the matching
    products in full, or a name-only overview when nothing matches.
    """
    return context_for_skus(tuple(p.sku for p in retrieve(question, products, k=k, history=history)), products, faq)


def context_for_skus(skus: tuple[str, ...], products: list[Product], faq: list[FaqItem]) -> Context:
    """The context for a given list of retrieved products (empty: the overview).

    Used to rebuild exactly what the model saw in a stored run, whatever the
    retriever does today.
    """
    by_sku = {p.sku: p for p in products}
    hits = [by_sku[sku] for sku in skus]
    catalog = "\n\n".join(render_product(p) for p in hits) if hits else render_overview(products)
    return Context(faq=render_faq(faq), catalog=catalog, skus=tuple(skus))
