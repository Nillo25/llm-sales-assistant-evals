"""Measure the output guard on stored runs, without calling any model.

    python scripts/guard_replay.py reports/raw/<run>.json [more runs...]

For each run, the guard is applied to every stored reply, the checks run again
on what it lets through, and the result is compared with the unguarded run on
the very same replies (paired, so only the guard differs).
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evals.cases import load_suite  # noqa: E402
from evals.compare import compare, render_comparison  # noqa: E402
from evals.runner import apply_guard, load_run  # noqa: E402
from evals.text import ascii_fold, excerpt  # noqa: E402
from sales_assistant.catalog import load_catalog, load_faq  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("raw", type=Path, nargs="+")
    parser.add_argument("--out", type=Path, default=ROOT / "reports")
    args = parser.parse_args(argv)
    suite, products, faq = load_suite(), load_catalog(), load_faq()
    for raw in args.raw:
        meta, results = load_run(json.loads(raw.read_text(encoding="utf-8")))
        guarded, changes = apply_guard(results, suite, products=products, faq=faq, prompt_version=meta.prompt_version)
        before = {(r.case_id, r.run): r.passed for r in results}
        after = {(r.case_id, r.run): r for r in guarded}
        lines = [
            render_comparison(compare(results, guarded), meta, meta).replace(
                "# Comparison:", "# Output guard replay:", 1
            ).rstrip(),
            "",
            "## What the guard changed",
            "",
            "Candidate = the same stored replies after the guard. A change to a reply that passed",
            "every check is a possible false alarm and is marked.",
            "",
        ]
        for case_id, run, actions in changes:
            mark = " (reply had passed: check this one)" if before[(case_id, run)] else ""
            verdict = "passes now" if after[(case_id, run)].passed else "still fails"
            lines.append(f"- {case_id} run {run}{mark}, {verdict}: {excerpt('; '.join(actions), 200)}")
        if not changes:
            lines.append("Nothing.")
        path = args.out / f"guard_replay_{raw.stem}.md"
        path.write_text(ascii_fold("\n".join(lines) + "\n"), encoding="ascii")
        false_alarms = sum(1 for c, r, _ in changes if before[(c, r)])
        print(f"{raw.stem}: {len(changes)} replies changed, {false_alarms} of them had passed; {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
