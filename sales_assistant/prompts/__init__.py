"""Versioned system prompts.

Each version is a plain text file next to this module, so prompt changes show
up as readable diffs and can be compared head to head by the eval runner.
"""
from functools import cache
from pathlib import Path

_DIR = Path(__file__).parent


def available_prompts() -> list[str]:
    return sorted(p.stem for p in _DIR.glob("*.txt"))


@cache
def load_prompt(version: str) -> str:
    path = _DIR / f"{version}.txt"
    if not path.is_file():
        raise ValueError(f"Unknown prompt version {version!r}; available: {', '.join(available_prompts())}")
    return path.read_text(encoding="utf-8").strip()
