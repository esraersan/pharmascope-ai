"""Database-backed signal tests using an isolated fixed snapshot."""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pharmascope.config.database import Base
from pharmascope.ingestion.models import DataSnapshot, DrugEventPair
from pharmascope.signals.calculator import compute_signals


def _pair(report_id: str, drug: str, event: str, snapshot: str = "fixed"):
    return DrugEventPair(
        report_id=report_id,
        snapshot_id=snapshot,
        drug_name=drug,
        drug_name_normalized=drug,
        drug_role="primary_suspect",
        event_term=event,
        event_term_normalized=event,
    )


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_signals_use_only_the_requested_complete_snapshot(db: Session):
    db.add(
        DataSnapshot(
            snapshot_id="fixed",
            source_url="https://example.test/fixed",
            sha256="a" * 64,
            period_end=datetime(2004, 1, 1),
            report_count=115,
            is_complete=True,
        )
    )
    db.add_all(
        [
            *[_pair(f"a{i}", "drug-x", "event-y") for i in range(10)],
            *[_pair(f"b{i}", "other", "event-y") for i in range(2)],
            *[_pair(f"c{i}", "drug-x", "other") for i in range(3)],
            *[_pair(f"d{i}", "other", "other") for i in range(100)],
            _pair("noise", "drug-x", "event-y", snapshot="adhoc"),
        ]
    )
    db.commit()

    scores = compute_signals("drug-x", db, snapshot_id="fixed")
    target = next(score for score in scores if score.event_term == "event-y")

    assert target.report_count == 10
    assert target.snapshot_id == "fixed"
    assert target.is_signal


def test_incomplete_snapshot_is_rejected(db: Session):
    db.add(
        DataSnapshot(
            snapshot_id="partial",
            source_url="https://example.test/partial",
            sha256="b" * 64,
            is_complete=False,
        )
    )
    db.commit()

    with pytest.raises(ValueError, match="No complete FAERS snapshot"):
        compute_signals("drug-x", db, snapshot_id="partial")
