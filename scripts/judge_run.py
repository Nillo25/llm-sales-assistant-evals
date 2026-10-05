"""Score a stored eval run with an LLM judge (DeepEval) and write a judge report.

    python scripts/judge_run.py reports/raw/<run>.json
    python scripts/judge_run.py reports/raw/<run>.json --judge-model gpt-4.1 --runs 1,2,3

Judges stored replies only: the assistant is not called again.
Needs: pip install -r requirements-judge.txt, and OPENAI_API_KEY (environment or .env).
"""
import argparse
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from evals.cases import load_suite  # noqa: E402
from evals.judge import DeepEvalScorer, JudgeMeta, judge_results, render_judge_report  # noqa: E402
from evals.runner import load_run  # noqa: E402
from sales_assistant.catalog import load_catalog, load_faq  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("raw", type=Path, help="raw run file from scripts/run_evals.py")
    parser.add_argument("--judge-model", default=os.environ.get("JUDGE_MODEL", "gpt-4.1"))
    parser.add_argument("--runs", default="1", help="comma-separated run numbers to judge (default: 1)")
    parser.add_argument("--workers", type=int, default=2, help="parallel judgments (default 2; judge models have low rate limits)")
    parser.add_argument("--out", type=Path, default=ROOT / "reports")
    args = parser.parse_args(argv)

    load_dotenv(ROOT / ".env")
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set: export it or put it in .env")

    meta, results = load_run(json.loads(args.raw.read_text(encoding="utf-8")))
    runs = tuple(int(r) for r in args.runs.split(","))
    print(f"Judging runs {runs} of {args.raw.name} with {args.judge_model}")

    t0 = time.perf_counter()
    judgments = judge_results(
        results,
        load_suite(),
        products=load_catalog(),
        faq=load_faq(),
        scorer=DeepEvalScorer(args.judge_model),
        runs=runs,
        workers=args.workers,
    )
    jmeta = JudgeMeta(args.raw.stem, meta.model, meta.prompt_version, args.judge_model, runs, time.perf_counter() - t0)

    stem = f"{args.raw.stem}_judge"
    (args.out / "raw").mkdir(parents=True, exist_ok=True)
    report_path = args.out / f"{stem}.md"
    report_path.write_text(render_judge_report(judgments, results, jmeta), encoding="ascii")
    raw_path = args.out / "raw" / f"{stem}.json"
    raw_path.write_text(json.dumps([asdict(j) for j in judgments], indent=2), encoding="utf-8")

    failed = sum(1 for j in judgments if not j.error and not j.passed)
    errors = sum(1 for j in judgments if j.error)
    print(f"Judgments: {len(judgments)}, failed: {failed}, errors: {errors}, cost: ${sum(j.cost for j in judgments):.2f}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
