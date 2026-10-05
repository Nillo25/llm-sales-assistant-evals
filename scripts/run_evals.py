"""Run the eval suite against a live model and write a Markdown report.

    python scripts/run_evals.py --model gpt-4.1-mini --prompt v1 --runs 3
    python scripts/run_evals.py --cases follow_up,pi-04 --runs 5
    python scripts/run_evals.py --rescore reports/raw/<run>.json   # re-check stored replies, no API calls

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
from evals.runner import RunMeta, dump_run, load_run, render_report, rescore, run_suite, summarize  # noqa: E402
from sales_assistant.catalog import load_catalog, load_faq  # noqa: E402
from sales_assistant.client import OpenAIResponder  # noqa: E402
from sales_assistant.prompts import available_prompts  # noqa: E402


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default=os.environ.get("EVAL_MODEL", "gpt-4.1-mini"))
    parser.add_argument("--prompt", default="v1", choices=available_prompts())
    parser.add_argument("--runs", type=int, default=3, help="runs per case (default 3)")
    parser.add_argument("--workers", type=int, default=4, help="parallel requests (default 4)")
    parser.add_argument("--cases", help="comma-separated case ids and/or categories (default: all)")
    parser.add_argument("--out", type=Path, default=ROOT / "reports")
    parser.add_argument("--rescore", type=Path, metavar="RAW_JSON", help="re-check a stored run with the current checks")
    return parser.parse_args(argv)


def select(suite: Suite, spec: str | None) -> Suite:
    if not spec:
        return suite
    wanted = {s.strip() for s in spec.split(",") if s.strip()}
    cases = tuple(c for c in suite.cases if c.id in wanted or c.category in wanted)
    if not cases:
        sys.exit(f"No cases match {spec!r}")
    return Suite(suite.competitor_brands, cases)


def write_outputs(out: Path, stem: str, meta: RunMeta, results) -> None:
    summary = summarize(results)
    (out / "raw").mkdir(parents=True, exist_ok=True)
    report_path = out / f"{stem}.md"
    report_path.write_text(render_report(summary, meta), encoding="ascii")
    raw_path = out / "raw" / f"{stem}.json"
    raw_path.write_text(json.dumps(dump_run(meta, results), indent=2), encoding="utf-8")
    print(f"Pass rate: {summary.passed_runs}/{summary.total_runs} runs, API errors: {summary.errors}")
    print(f"Report: {report_path.relative_to(ROOT)}\nRaw:    {raw_path.relative_to(ROOT)}")


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.rescore:
        meta, results = load_run(json.loads(args.rescore.read_text(encoding="utf-8")))
        results = rescore(results, load_suite(), products=load_catalog(), faq=load_faq(), prompt_version=meta.prompt_version)
        write_outputs(args.out, args.rescore.stem, meta, results)
        return 0

    load_dotenv(ROOT / ".env")
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set: export it or put it in .env")

    suite = select(load_suite(), args.cases)
    calls = len(suite.cases) * args.runs
    print(f"{len(suite.cases)} cases x {args.runs} runs = {calls} calls to {args.model} (prompt {args.prompt})")

    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    results = run_suite(
        suite,
        responder=OpenAIResponder(),
        model=args.model,
        prompt_version=args.prompt,
        runs=args.runs,
        workers=args.workers,
        products=load_catalog(),
        faq=load_faq(),
    )
    meta = RunMeta(args.model, args.prompt, args.runs, f"{started:%Y-%m-%d %H:%M} UTC", time.perf_counter() - t0)
    stem = f"{started:%Y-%m-%d}_{args.model}_{args.prompt}" + (f"_{args.cases.replace(',', '+')}" if args.cases else "")
    write_outputs(args.out, stem, meta, results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
