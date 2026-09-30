"""Import a checksummed, immutable FAERS reference snapshot."""

from __future__ import annotations

import gzip
import hashlib
import json
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile

from sqlalchemy.orm import Session

from pharmascope.ingestion.fetcher import parse_report
from pharmascope.ingestion.models import (
    AdverseEventReport,
    DataSnapshot,
    DrugEventPair,
)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Return the SHA-256 digest for a local source artifact."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _records_from_json_text(text: str) -> Iterator[dict]:
    """Read either an openFDA JSON object/list or newline-delimited JSON."""
    stripped = text.lstrip()
    if not stripped:
        return
    if stripped[0] in "[{":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None
        if payload is not None:
            if isinstance(payload, dict):
                yield from payload.get("results", [])
            elif isinstance(payload, list):
                yield from payload
            return
    for line in text.splitlines():
        if line.strip():
            yield json.loads(line)


def iter_faers_records(path: Path) -> Iterator[dict]:
    """Yield reports from JSON, JSONL, gzip, or openFDA zip exports."""
    suffixes = path.suffixes
    if suffixes and suffixes[-1] == ".zip":
        with ZipFile(path) as archive:
            for name in sorted(archive.namelist()):
                if name.endswith((".json", ".jsonl", ".ndjson")):
                    yield from _records_from_json_text(
                        archive.read(name).decode("utf-8")
                    )
        return
    if suffixes and suffixes[-1] == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            yield from _records_from_json_text(handle.read())
        return
    yield from _records_from_json_text(path.read_text(encoding="utf-8"))


def import_snapshot(
    path: Path,
    db: Session,
    *,
    snapshot_id: str,
    source_url: str,
    expected_sha256: str,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
) -> DataSnapshot:
    """Import one validated snapshot and mark it complete atomically.

    A complete snapshot is immutable. Failed imports are rolled back, so signal
    analysis can never silently use a partially loaded reference population.
    """
    actual_sha256 = sha256_file(path)
    if actual_sha256 != expected_sha256.lower():
        raise ValueError(
            f"Checksum mismatch for {path}: expected {expected_sha256}, "
            f"got {actual_sha256}"
        )

    existing_snapshot = db.get(DataSnapshot, snapshot_id)
    if existing_snapshot and existing_snapshot.is_complete:
        raise ValueError(f"Snapshot '{snapshot_id}' is complete and immutable")

    try:
        if existing_snapshot is None:
            snapshot = DataSnapshot(
                snapshot_id=snapshot_id,
                source_url=source_url,
                sha256=actual_sha256,
                period_start=period_start,
                period_end=period_end,
                is_complete=False,
            )
            db.add(snapshot)
        else:
            snapshot = existing_snapshot

        latest_versions: dict[str, int] = {}
        report_count = 0
        for raw in iter_faers_records(path):
            report, pairs = parse_report(raw, snapshot_id=snapshot_id)
            report_id = report["report_id"]
            if not report_id:
                continue

            version = report["report_version"]
            seen_version = latest_versions.get(report_id, 0)
            if version < seen_version:
                continue

            existing_report = (
                db.query(AdverseEventReport)
                .filter_by(report_id=report_id, snapshot_id=snapshot_id)
                .first()
            )
            if existing_report and existing_report.report_version > version:
                continue
            if existing_report:
                db.query(DrugEventPair).filter_by(
                    report_id=report_id,
                    snapshot_id=snapshot_id,
                ).delete()
                for key, value in report.items():
                    setattr(existing_report, key, value)
            else:
                db.add(AdverseEventReport(**report))
                report_count += 1

            unique_pairs = {
                (
                    pair["drug_name_normalized"],
                    pair["drug_role"],
                    pair["event_term_normalized"],
                ): pair
                for pair in pairs
            }
            db.add_all(DrugEventPair(**pair) for pair in unique_pairs.values())
            latest_versions[report_id] = version

        snapshot.report_count = report_count
        snapshot.is_complete = True
        db.commit()
        db.refresh(snapshot)
        return snapshot
    except Exception:
        db.rollback()
        raise
