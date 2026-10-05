"""Check the LLM judge against human labels (evals/judge_calibration.yaml).

    python scripts/calibrate_judge.py
    python scripts/calibrate_judge.py --strict-faithfulness --judge-model gpt-4.1

Needs: pip install -r requirements-judge.txt, and OPENAI_API_KEY (environment or .env).
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from evals.calibration import load_calibration, render_calibration_report, run_calibration  # noqa: E402
from evals.cases import load_suite  # noqa: E402
from evals.judge import DeepEvalScorer  # noqa: E402
from sales_assistant.catalog import load_catalog, load_faq  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--judge-model", default=os.environ.get("JUDGE_MODEL", "gpt-4.1"))
    parser.add_argument("--strict-faithfulness", action="store_true", help="also fail claims the context does not support")
    parser.add_argument("--workers", type=int, default=2, help="parallel judgments (default 2; judge models have low rate limits)")
    parser.add_argument("--out", type=Path, default=ROOT / "reports")
    args = parser.parse_args(argv)

    load_dotenv(ROOT / ".env")
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set: export it or put it in .env")

    suite = load_suite()
    items = load_calibration(suite)
    variant = "strict faithfulness" if args.strict_faithfulness else "default faithfulness"
    results = run_calibration(
        items,
        suite,
        products=load_catalog(),
        faq=load_faq(),
        scorer=DeepEvalScorer(args.judge_model, strict_faithfulness=args.strict_faithfulness),
        workers=args.workers,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"judge_calibration_{args.judge_model}_{'strict' if args.strict_faithfulness else 'default'}.md"
    path.write_text(render_calibration_report(results, args.judge_model, variant), encoding="ascii")
    print(f"Agreement: {sum(r.agrees for r in results)}/{len(results)}")
    print(f"Report: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
