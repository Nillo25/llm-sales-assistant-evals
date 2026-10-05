"""Compare two stored eval runs (baseline vs candidate) without calling any model.

    python scripts/compare_runs.py reports/raw/<baseline>.json reports/raw/<candidate>.json
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evals.compare import compare, render_comparison  # noqa: E402
from evals.runner import load_run  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--out", type=Path, default=ROOT / "reports")
    args = parser.parse_args(argv)

    base_meta, base = load_run(json.loads(args.baseline.read_text(encoding="utf-8")))
    cand_meta, cand = load_run(json.loads(args.candidate.read_text(encoding="utf-8")))
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"compare_{args.baseline.stem}_vs_{args.candidate.stem}.md"
    path.write_text(render_comparison(compare(base, cand), base_meta, cand_meta), encoding="ascii")
    print(f"Comparison: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
