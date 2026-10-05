"""The NO_ANSWER service marker.

The model is asked to start its reply with NO_ANSWER when it does not answer
on the merits (off-topic or unintelligible message). The application uses the
flag to decide whether to offer a rating under the reply, and strips the
marker so the customer never sees it.
"""
import re

NO_ANSWER_MARKER = "NO_ANSWER"
_MARKER_RE = re.compile(rf"{NO_ANSWER_MARKER}\s*:?", re.IGNORECASE)


def split_no_answer_marker(raw: str | None) -> tuple[str, bool]:
    """Return (text without the marker, whether the marker was present).

    The marker is removed from anywhere in the text, not only from the start:
    models do not always place it where they were asked to.
    """
    text = (raw or "").strip()
    if not text or not _MARKER_RE.search(text):
        return (text, False)
    cleaned = _MARKER_RE.sub(" ", text)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return (cleaned, True)
