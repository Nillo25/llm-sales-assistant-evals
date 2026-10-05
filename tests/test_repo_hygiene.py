"""Repository hygiene: every text file is plain ASCII.

Keeps out smart quotes, invisible characters and stray non-English text
that tend to sneak in through copy-paste.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", "raw"}
TEXT_SUFFIXES = {"", ".py", ".md", ".txt", ".yaml", ".yml", ".toml", ".cfg", ".ini", ".json", ".sh"}


def text_files(root: Path = ROOT):
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts) or not path.is_file():
            continue
        if path.suffix in TEXT_SUFFIXES:
            yield path


def non_ascii_lines(path: Path) -> list[int]:
    data = path.read_bytes()
    return [n for n, line in enumerate(data.splitlines(), 1) if any(b > 127 for b in line)]


def test_detector_reports_non_ascii_lines(tmp_path):
    sample = tmp_path / "sample.md"
    sample.write_text("plain\ncaf\u00e9\nplain\n", encoding="utf-8")
    assert non_ascii_lines(sample) == [2]
    assert list(text_files(tmp_path)) == [sample]


def test_repository_text_files_are_ascii():
    offenders = {
        str(path.relative_to(ROOT)): lines for path in text_files() if (lines := non_ascii_lines(path))
    }
    assert not offenders, f"non-ASCII characters in {offenders}"


def test_deepeval_pytest_plugin_is_disabled(pytestconfig):
    # DeepEval's auto-loaded pytest plugin reports telemetry at session start,
    # before any code here can opt out. The suite calls metrics directly and
    # does not need the plugin.
    assert not pytestconfig.pluginmanager.has_plugin("deepeval")
