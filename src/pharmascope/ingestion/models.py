"""Database models for FAERS adverse event data."""

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from pharmascope.config.database import Base


def utc_now() -> datetime:
    """Return an aware UTC timestamp for persistence defaults."""
    return datetime.now(UTC)


class AdverseEventReport(Base):
    """A single FAERS adverse event report."""

    __tablename__ = "adverse_event_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[str] = mapped_column(String(50), nullable=False)
    report_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    snapshot_id: Mapped[str] = mapped_column(String(100), nullable=False)
    receive_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reporter_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(100), nullable=True)
    primary_drug: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    __table_args__ = (
        UniqueConstraint(
            "snapshot_id",
            "report_id",
            name="uq_snapshot_report",
        ),
        Index("ix_adverse_event_reports_report_id", "report_id"),
        Index("ix_adverse_event_reports_snapshot_id", "snapshot_id"),
        Index("ix_adverse_event_reports_primary_drug", "primary_drug"),
    )


class DrugEventPair(Base):
    """A drug-event pair extracted from a FAERS report."""

    __tablename__ = "drug_event_pairs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[str] = mapped_column(String(50), nullable=False)
    snapshot_id: Mapped[str] = mapped_column(String(100), nullable=False)
    drug_name: Mapped[str] = mapped_column(String(255), nullable=False)
    drug_name_normalized: Mapped[str | None] = mapped_column(String(255), nullable=True)
    drug_role: Mapped[str] = mapped_column(String(30), nullable=False)
    event_term: Mapped[str] = mapped_column(String(255), nullable=False)
    event_term_normalized: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    __table_args__ = (
        UniqueConstraint(
            "snapshot_id",
            "report_id",
            "drug_name_normalized",
            "drug_role",
            "event_term_normalized",
            name="uq_snapshot_report_drug_role_event",
        ),
        Index(
            "ix_drug_event_pairs_snapshot_drug",
            "snapshot_id",
            "drug_name_normalized",
        ),
        Index("ix_drug_event_pairs_event_term", "event_term_normalized"),
    )


class DataSnapshot(Base):
    """An immutable, versioned FAERS reference population."""

    __tablename__ = "data_snapshots"

    snapshot_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    period_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    report_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class SignalResult(Base):
    """Computed PRR/ROR signal for a drug-event pair."""

    __tablename__ = "signal_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    drug_name: Mapped[str] = mapped_column(String(255), nullable=False)
    event_term: Mapped[str] = mapped_column(String(255), nullable=False)
    report_count: Mapped[int] = mapped_column(Integer, nullable=False)
    prr: Mapped[float | None] = mapped_column(Float, nullable=True)
    prr_lower_ci: Mapped[float | None] = mapped_column(Float, nullable=True)
    prr_upper_ci: Mapped[float | None] = mapped_column(Float, nullable=True)
    ror: Mapped[float | None] = mapped_column(Float, nullable=True)
    ror_lower_ci: Mapped[float | None] = mapped_column(Float, nullable=True)
    ror_upper_ci: Mapped[float | None] = mapped_column(Float, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    __table_args__ = (
        Index("ix_signal_results_drug_name", "drug_name"),
    )
