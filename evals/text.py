"""Text helpers: punctuation normalization, plain ASCII reports, one-line excerpts."""
import unicodedata

_PUNCT = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-",
                        "\u2026": "...", "\u00a0": " ", "\u2022": "-"})


def normalize_punctuation(text: str) -> str:
    """Typographic quotes, dashes and spaces to ASCII, so patterns match however a model types them."""
    return text.translate(_PUNCT)


def ascii_fold(text: str) -> str:
    """Model replies may contain typographic characters; reports stay plain ASCII."""
    folded = unicodedata.normalize("NFKD", normalize_punctuation(text))
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return folded.encode("ascii", "backslashreplace").decode("ascii")


def excerpt(text: str, limit: int = 280) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 3] + "..."
