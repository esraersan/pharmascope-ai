"""Snapshot import tests cover checksums and atomic completeness."""

import hashlib
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pharmascope.config.database import Base
from pharmascope.ingestion.models import DataSnapshot, DrugEventPair
from pharmascope.ingestion.snapshot import import_snapshot


def test_import_snapshot_validates_and_marks_complete(tmp_path):
    payload = {
        "results": [
            {
                "safetyreportid": "1",
                "safetyreportversion": "1",
                "receivedate": "20040101",
                "patient": {
                    "drug": [
                        {
                            "medicinalproduct": "Drug X",
                            "drugcharacterization": "1",
                        }
                    ],
                    "reaction": [{"reactionmeddrapt": "Event Y"}],
                },
            }
        ]
    }
    path = tmp_path / "snapshot.json"
    raw = json.dumps(payload).encode()
    path.write_bytes(raw)
    checksum = hashlib.sha256(raw).hexdigest()

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        snapshot = import_snapshot(
            path,
            db,
            snapshot_id="test",
            source_url="https://example.test",
            expected_sha256=checksum,
        )

        assert snapshot.is_complete
        assert snapshot.report_count == 1
        assert db.query(DrugEventPair).one().drug_role == "primary_suspect"


def test_checksum_mismatch_does_not_create_snapshot(tmp_path):
    path = tmp_path / "snapshot.json"
    path.write_text("[]", encoding="utf-8")
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        with pytest.raises(ValueError, match="Checksum mismatch"):
            import_snapshot(
                path,
                db,
                snapshot_id="test",
                source_url="https://example.test",
                expected_sha256="0" * 64,
            )
        assert db.query(DataSnapshot).count() == 0
