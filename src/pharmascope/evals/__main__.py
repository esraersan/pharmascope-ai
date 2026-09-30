"""Command-line interface for evaluating pre-recorded candidate responses."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from pharmascope.evals.io import load_jsonl, load_tasks, write_jsonl
from pharmascope.evals.models import CandidateResponse
from pharmascope.evals.runner import evaluate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m pharmascope.evals",
        description="Grade structured candidate responses without model calls.",
    )
    parser.add_argument("--tasks", required=True, help="Task JSON or JSONL path")
    parser.add_argument(
        "--responses", required=True, help="Candidate response JSONL path"
    )
    parser.add_argument("--report", required=True, help="Output report JSON path")
    parser.add_argument(
        "--results-jsonl", help="Optional per-task result JSONL output path"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    tasks = load_tasks(args.tasks)
    responses = load_jsonl(args.responses, CandidateResponse)
    report = evaluate(tasks, responses)

    destination = Path(args.report)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.results_jsonl:
        write_jsonl(args.results_jsonl, report.results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
