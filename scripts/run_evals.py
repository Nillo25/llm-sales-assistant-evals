"""Run the eval suite against a live model and write a Markdown report.

    python scripts/run_evals.py --model gpt-4.1-mini --prompt v1 --runs 3
    python scripts/run_evals.py --cases follow_up,pi-04 --runs 5
    python scripts/run_evals.py --rescore reports/raw/<run>.json   # re-check stored replies, no API calls
    python scripts/run_evals.py --compare-model gpt-5.4-mini           # baseline vs candidate, plus a comparison
    python scripts/run_evals.py --fail-under 0.75                       # exit 1 if the pass rate is lower (CI gate)

Reads OPENAI_API_KEY from the environment or from a .env file in the repo root.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from evals.cases import Suite, load_suite  # noqa: E402
from evals.compare import compare, render_comparison  # noqa: E402
from evals.runner import (  # noqa: E402
    RunMeta,
    below_threshold,
    dump_run,
    load_run,
    render_report,
    rescore,
    run_suite,
    summarize,
)
from sales_assistant.catalog import load_catalog, load_faq  # noqa: E402
from sales_assistant.client import OpenAIResponder  # noqa: E402
from sales_assistant.prompts import available_prompts  # noqa: E402
from sales_assistant.retriever import RETRIEVAL_VERSION  # noqa: E402


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default=os.environ.get("EVAL_MODEL", "gpt-4.1-mini"))
    parser.add_argument("--prompt", default="v1", choices=available_prompts())
    parser.add_argument("--runs", type=int, default=3, help="runs per case (default 3)")
    parser.add_argument("--workers", type=int, default=4, help="parallel requests (default 4)")
    parser.add_argument("--cases", help="comma-separated case ids, categories and/or splits (dev, holdout); default: all")
    parser.add_argument("--out", type=Path, default=ROOT / "reports")
    parser.add_argument("--rescore", type=Path, metavar="RAW_JSON", help="re-check a stored run with the current checks")
    parser.add_argument("--compare-model", help="also run this model and compare it with --model")
    parser.add_argument("--compare-prompt", choices=available_prompts(), help="also run this prompt and compare")
    parser.add_argument("--fail-under", type=float, metavar="RATE", help="exit 1 if the overall pass rate is below RATE (0-1)")
    return parser.parse_args(argv)


def write_outputs(out: Path, stem: str, meta: RunMeta, results, fail_under: float | None = None) -> bool:
    """Write the report and the raw run; return True if the quality gate is failed."""
    summary = summarize(results)
    (out / "raw").mkdir(parents=True, exist_ok=True)
    report_path = out / f"{stem}.md"
    report_path.write_text(render_report(summary, meta), encoding="ascii")
    raw_path = out / "raw" / f"{stem}.json"
    raw_path.write_text(json.dumps(dump_run(meta, results), indent=2), encoding="utf-8")
    print(f"Pass rate: {summary.passed_runs}/{summary.total_runs} runs, API errors: {summary.errors}")
    print(f"Report: {report_path}\nRaw:    {raw_path}")
    return below_threshold(summary, fail_under)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.rescore:
        meta, results = load_run(json.loads(args.rescore.read_text(encoding="utf-8")))
        results = rescore(results, load_suite(), products=load_catalog(), faq=load_faq(), prompt_version=meta.prompt_version)
        return int(write_outputs(args.out, args.rescore.stem, meta, results, args.fail_under))

    load_dotenv(ROOT / ".env")
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set: export it or put it in .env")

    try:
        suite = load_suite().select(args.cases)
    except ValueError as exc:
        sys.exit(str(exc))
    base_meta, base_results, failed = run_config(args, suite, args.model, args.prompt)
    if not (args.compare_model or args.compare_prompt):
        return int(failed)

    cand_meta, cand_results, cand_failed = run_config(
        args, suite, args.compare_model or args.model, args.compare_prompt or args.prompt
    )
    path = args.out / f"compare_{stem_for(args, base_meta)}_vs_{stem_for(args, cand_meta)}.md"
    path.write_text(render_comparison(compare(base_results, cand_results), base_meta, cand_meta), encoding="ascii")
    print(f"Comparison: {path}")
    return int(failed or cand_failed)


def stem_for(args, meta: RunMeta) -> str:
    stem = f"{meta.started_at[:10]}_{meta.model}_{meta.prompt_version}_{meta.retrieval}"
    return stem + (f"_{args.cases.replace(',', '+')}" if args.cases else "")


def run_config(args, suite: Suite, model: str, prompt: str):
    print(f"{len(suite.cases)} cases x {args.runs} runs = {len(suite.cases) * args.runs} calls to {model} (prompt {prompt})")
    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    results = run_suite(
        suite,
        responder=OpenAIResponder(),
        model=model,
        prompt_version=prompt,
        runs=args.runs,
        workers=args.workers,
        products=load_catalog(),
        faq=load_faq(),
    )
    meta = RunMeta(model, prompt, args.runs, f"{started:%Y-%m-%d %H:%M} UTC", time.perf_counter() - t0, RETRIEVAL_VERSION)
    failed = write_outputs(args.out, stem_for(args, meta), meta, results, args.fail_under)
    return meta, results, failed

if __name__ == "__main__":
    sys.exit(main())
