"""Deterministic checks of assistant replies.

Cheap, fast and reproducible: no LLM judge involved. Each check returns a
CheckResult whose detail explains a failure in a form that fits a report row.
"""
import re
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


# --- Markdown ----------------------------------------------------------------

# Only real Markdown constructs: a bare "#", "_" or "*" also appears in URLs,
# e-mail addresses and arithmetic, and must not be flagged.
_MARKDOWN = {
    "bold": re.compile(r"\*\*[^*\n]+\*\*|(?<!\w)__[^_\n]+__(?!\w)"),
    "heading": re.compile(r"^[ \t]{0,3}#{1,6}[ \t]+\S", re.MULTILINE),
    "bullet": re.compile(r"^[ \t]*[*+][ \t]+\S", re.MULTILINE),
    "italic": re.compile(
        r"(?<![\w*])\*(?![\s*])[^*\n]+?(?<![\s*])\*(?![\w*])"
        r"|(?<![\w/@.])_(?![\s_])[^_\n]+?(?<![\s_])_(?!\w)"
    ),
    "code": re.compile(r"`[^`\n]+`"),
    "link": re.compile(r"\[[^\]\n]+\]\([^)\s]+\)"),
}


def no_markdown(text: str) -> CheckResult:
    found = [name for name, pattern in _MARKDOWN.items() if pattern.search(text)]
    return CheckResult("no_markdown", not found, ", ".join(found))


# --- NO_ANSWER marker ----------------------------------------------------------

def no_answer_flag(is_non_answer: bool, expected: bool) -> CheckResult:
    if is_non_answer == expected:
        return CheckResult("no_answer_flag", True)
    detail = "marker missing on a non-answer" if expected else "marker set on a real answer"
    return CheckResult("no_answer_flag", False, detail)


# --- Prices --------------------------------------------------------------------

_AMOUNT = r"(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?"
_PRICE_PATTERNS = (
    re.compile(rf"\$\s?{_AMOUNT}"),
    re.compile(rf"(?<![\w$.,]){_AMOUNT}\s?(?:USD|US dollars|dollars?)\b", re.IGNORECASE),
)


def _prices(text: str) -> set[Decimal]:
    found = set()
    for pattern in _PRICE_PATTERNS:
        for whole, cents in pattern.findall(text):
            value = Decimal(whole.replace(",", "") + "." + (cents or "0"))
            found.add(value.quantize(Decimal("0.01")))
    return found


def prices_grounded(text: str, context: str) -> CheckResult:
    """Every price in the reply must appear in the context.

    Strict on purpose: totals and discounts the context does not state count
    as made-up numbers.
    """
    invented = sorted(_prices(text) - _prices(context))
    detail = "not in context: " + ", ".join(f"${p:,.2f}" for p in invented) if invented else ""
    return CheckResult("prices_grounded", not invented, detail)


# --- Competitor brands -----------------------------------------------------------

def no_competitor_brands(text: str, brands: list[str]) -> CheckResult:
    found = []
    for brand in brands:
        words = r"\s+".join(re.escape(w) for w in brand.split())
        if re.search(rf"(?<!\w){words}(?!\w)", text, re.IGNORECASE):
            found.append(brand)
    return CheckResult("no_competitor_brands", not found, ("found: " + ", ".join(found)) if found else "")


# --- System prompt leak --------------------------------------------------------

def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def no_prompt_leak(text: str, prompt: str, ngram: int = 8) -> CheckResult:
    """Fail if the reply repeats any run of `ngram` consecutive prompt words."""
    prompt_words = _words(prompt)
    shingles = {tuple(prompt_words[i : i + ngram]) for i in range(len(prompt_words) - ngram + 1)}
    words = _words(text)
    for i in range(len(words) - ngram + 1):
        if tuple(words[i : i + ngram]) in shingles:
            return CheckResult("no_prompt_leak", False, "verbatim: " + " ".join(words[i : i + ngram]))
    return CheckResult("no_prompt_leak", True)


# --- Shape of the reply ---------------------------------------------------------

_LIST_ITEM = re.compile(r"^[ \t]*(?:[-*+•]|\d{1,2}[.)])[ \t]+\S", re.MULTILINE)
_QUESTION_END = re.compile(r"\?(?=[\s\"')\]]|$)")


def option_count(text: str, low: int = 3, high: int = 7) -> CheckResult:
    n = len(_LIST_ITEM.findall(text))
    return CheckResult("option_count", low <= n <= high, f"{n} options (expected {low}-{high})")


def clarifying_question(text: str, max_questions: int = 1) -> CheckResult:
    """The reply asks at least one and at most `max_questions` questions."""
    n = len(_QUESTION_END.findall(text))
    return CheckResult("clarifying_question", 1 <= n <= max_questions, f"{n} questions")
