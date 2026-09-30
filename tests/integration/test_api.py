"""API contract tests against an isolated database."""

from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from pharmascope.api.main import app
from pharmascope.config.database import Base, get_db
from pharmascope.ingestion.models import DataSnapshot


def test_analyze_requires_a_complete_snapshot():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def override_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).post(
            "/analyze",
            json={"drug_name": "rofecoxib"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert "complete FAERS snapshot" in response.json()["detail"]


def test_snapshots_exposes_provenance():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            DataSnapshot(
                snapshot_id="fixed",
                source_url="https://example.test",
                sha256="a" * 64,
                period_end=datetime(2020, 12, 31),
                report_count=12,
                is_complete=True,
            )
        )
        session.commit()

    def override_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/snapshots")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["snapshot_id"] == "fixed"
    assert response.json()[0]["sha256"] == "a" * 64
