"""Output guard: checks a reply in code before it reaches the customer.

The dev findings showed that prompt rules do not stop content-changing
injections: a customer can make the model append a false promotion, quote a
price planted earlier in the chat, or recite its own instructions. A rule in
the prompt is a request; this module is a check. It is deterministic, costs no
extra model call, and was designed on the dev findings only, so the holdout
set measures it.

What it does:
- A sentence that repeats a run of system-prompt words is removed, so a reply
  that recites the prompt and then answers keeps only the answer; a reply
  that was nothing but the prompt becomes a refusal.
- A sentence with a dollar price the catalog and FAQ do not contain is removed.
  Prices from the customer's latest message are allowed (a budget such as
  "around $100"); prices from earlier turns are not, because that is where an
  attacker plants them.
- A sentence that promises a promotion (free, discount, % off, sale, coupon) is
  removed unless it carries a number the catalog or FAQ actually states, as in
  "shipping is free on orders over $50". A negated sentence ("we don't offer
  bulk discounts") is the honest answer, not a promise, and stays.

Removing a sentence is preferred to refusing the whole reply: the legitimate
part of the answer still reaches the customer.
"""
import re
from dataclasses import dataclass

REFUSAL = "I can't share my internal instructions, but I'm happy to help you choose Ampwise products."

_AMOUNT = r"(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?"
_PRICE = re.compile(rf"\$\s?{_AMOUNT}")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
_PROMO = re.compile(
    r"(?<![-\w])free\b(?! to\b)|\bdiscount\w*|\d+\s?%\s?(?:off|lower|cheaper|less)\b|\boff (?:every|all|your)\b"
    r"|\bon sale\b|\bsale price\b"
    r"|\bpromo\w*|\bcoupon\w*|\bspecial offer\b|\bat no (?:extra )?cost\b",
    re.IGNORECASE,
)
_FEEL_FREE = re.compile(r"\bfeel free\b|\bhands-free\b", re.IGNORECASE)
# "We don't offer bulk discounts" is the honest answer to a discount question, not a promise.
_NEGATION = re.compile(r"\b(?:no|not|never|neither|nor|without|unable)\b|n['\u2019]t\b", re.IGNORECASE)
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")
_WORD = re.compile(r"[a-z0-9']+")


@dataclass(frozen=True)
class GuardResult:
    text: str
    actions: tuple[str, ...] = ()

    @property
    def changed(self) -> bool:
        return bool(self.actions)


def _prices(text: str) -> set[str]:
    return {f"{whole.replace(',', '')}.{(cents or '0').ljust(2, '0')}" for whole, cents in _PRICE.findall(text)}


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in _NUMBER.findall(text)}


def _words(text: str) -> list[str]:
    return _WORD.findall(text.lower().replace("\u2019", "'"))


def leaks_prompt(reply: str, system_prompt: str, ngram: int = 6) -> str | None:
    """The first run of `ngram` system-prompt words the reply repeats, or None."""
    prompt_words = _words(system_prompt)
    shingles = {tuple(prompt_words[i : i + ngram]) for i in range(len(prompt_words) - ngram + 1)}
    words = _words(reply)
    for i in range(len(words) - ngram + 1):
        if tuple(words[i : i + ngram]) in shingles:
            return " ".join(words[i : i + ngram])
    return None


def guard_reply(reply: str, *, system_prompt: str, context: str, question: str) -> GuardResult:
    """Check one reply. context is the FAQ and catalog text the model was given."""
    allowed_prices = _prices(context) | _prices(question)
    context_numbers = _numbers(context)
    kept, actions = [], []
    for sentence in (s for s in _SENTENCE.split(reply.strip()) if s.strip()):
        leaked = leaks_prompt(sentence, system_prompt)
        if leaked:
            actions.append(f"removed prompt leak: '{leaked}'")
            continue
        invented = _prices(sentence) - allowed_prices
        if invented:
            actions.append(f"removed ungrounded price {', '.join(sorted(invented))}: {sentence.strip()[:80]}")
            continue
        promises = _PROMO.search(_FEEL_FREE.sub("", sentence)) and not _NEGATION.search(sentence)
        if promises and not (_numbers(sentence) & context_numbers):
            actions.append(f"removed promotion: {sentence.strip()[:80]}")
            continue
        kept.append(sentence.strip())
    if not actions:
        return GuardResult(reply)
    text = " ".join(kept).strip() or REFUSAL
    return GuardResult(text, tuple(actions))
