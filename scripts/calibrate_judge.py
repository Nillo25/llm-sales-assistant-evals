"""Check the LLM judge against human labels (evals/judge_calibration.yaml).

    python scripts/calibrate_judge.py
    python scripts/calibrate_judge.py --strict-faithfulness --judge-model claude-sonnet-5-5

Needs: pip install -r requirements-judge.txt, and ANTHROPIC_API_KEY for a Claude judge
(the default) or OPENAI_API_KEY for an OpenAI one (environment or .env).
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from evals.claude_judge import is_claude  # noqa: E402

from evals.calibration import load_calibration, render_calibration_report, run_calibration  # noqa: E402
from evals.cases import load_suite  # noqa: E402
from evals.judge import DEFAULT_JUDGE_MODEL, DeepEvalScorer  # noqa: E402
from sales_assistant.catalog import load_catalog, load_faq  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--judge-model", default=os.environ.get("JUDGE_MODEL", DEFAULT_JUDGE_MODEL))
    parser.add_argument("--effort", default="low", choices=("low", "medium", "high", "xhigh", "max"),
                        help="thinking effort for a Claude judge (default low)")
    parser.add_argument("--strict-faithfulness", action="store_true", help="also fail claims the context does not support")
    parser.add_argument("--workers", type=int, default=2, help="parallel judgments (default 2; judge models have low rate limits)")
    parser.add_argument("--repeats", type=int, default=1, help="run the whole calibration N times to measure judge variance")
    parser.add_argument("--out", type=Path, default=ROOT / "reports")
    args = parser.parse_args(argv)

    load_dotenv(ROOT / ".env")
    key = "ANTHROPIC_API_KEY" if is_claude(args.judge_model) else "OPENAI_API_KEY"
    if not os.environ.get(key):
        sys.exit(f"{key} is not set: export it or put it in .env")

    suite = load_suite()
    items = load_calibration(suite)
    variant = "strict faithfulness" if args.strict_faithfulness else "default faithfulness"
    scorer = DeepEvalScorer(args.judge_model, strict_faithfulness=args.strict_faithfulness, effort=args.effort)
    repeats = []
    for n in range(args.repeats):
        results = run_calibration(items, suite, products=load_catalog(), faq=load_faq(), scorer=scorer, workers=args.workers)
        repeats.append(results)
        print(f"Run {n + 1}/{args.repeats}: agreement {sum(r.agrees for r in results)}/{len(results)}")
    args.out.mkdir(parents=True, exist_ok=True)
    suffix = "strict" if args.strict_faithfulness else "default"
    if args.repeats > 1:
        suffix += f"_x{args.repeats}"
    path = args.out / f"judge_calibration_{args.judge_model}_{suffix}.md"
    path.write_text(render_calibration_report(repeats[0], args.judge_model, variant, repeats), encoding="ascii")
    print(f"Report: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
