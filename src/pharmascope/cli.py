"""Command-line entry points for reproducible data and evaluation workflows."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from pharmascope.config.database import Base, SessionLocal, engine
from pharmascope.evaluation.benchmark import (
    load_cases,
    load_observations,
    run_benchmark,
)
from pharmascope.ingestion.snapshot import import_snapshot, sha256_file


def _date(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def init_db() -> None:
    """Create the current schema for a new local development database."""
    # Importing models registers their tables with Base.metadata.
    import pharmascope.ingestion.models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def load_snapshot(manifest_path: Path) -> None:
    """Validate a manifest and import its local data artifact."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    data_path = (manifest_path.parent / manifest["file"]).resolve()
    with SessionLocal() as db:
        snapshot = import_snapshot(
            data_path,
            db,
            snapshot_id=manifest["snapshot_id"],
            source_url=manifest["source_url"],
            expected_sha256=manifest["sha256"],
            period_start=_date(manifest.get("period_start")),
            period_end=_date(manifest.get("period_end")),
        )
    print(
        f"Imported {snapshot.report_count} reports into "
        f"snapshot '{snapshot.snapshot_id}'."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pharmascope")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init-db", help="Create local database tables")

    checksum = commands.add_parser("checksum", help="Hash a snapshot artifact")
    checksum.add_argument("path", type=Path)

    load = commands.add_parser("load-snapshot", help="Import a snapshot manifest")
    load.add_argument("manifest", type=Path)

    benchmark = commands.add_parser(
        "benchmark",
        help="Run the temporal safety-signal benchmark",
    )
    benchmark.add_argument("observations", type=Path)
    benchmark.add_argument(
        "--cases",
        type=Path,
        default=Path("data/benchmark_cases.json"),
    )
    benchmark.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/benchmark"),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "init-db":
        init_db()
    elif args.command == "checksum":
        print(sha256_file(args.path))
    elif args.command == "load-snapshot":
        load_snapshot(args.manifest)
    elif args.command == "benchmark":
        summary = run_benchmark(
            load_observations(args.observations),
            load_cases(args.cases),
            args.output,
        )
        print(json.dumps(summary["metrics"], indent=2))


if __name__ == "__main__":
    main()
