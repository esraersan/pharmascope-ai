"""Database models for FAERS adverse event data."""

from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Float, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from pharmascope.config.database import Base


class AdverseEventReport(Base):
    """A single FAERS adverse event report."""

    __tablename__ = "adverse_event_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    receive_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reporter_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(100), nullable=True)
    primary_drug: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_adverse_event_reports_report_id", "report_id"),
        Index("ix_adverse_event_reports_primary_drug", "primary_drug"),
    )


class DrugEventPair(Base):
    """A drug-event pair extracted from a FAERS report."""

    __tablename__ = "drug_event_pairs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[str] = mapped_column(String(50), nullable=False)
    drug_name: Mapped[str] = mapped_column(String(255), nullable=False)
    drug_name_normalized: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_term: Mapped[str] = mapped_column(String(255), nullable=False)
    event_term_normalized: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_drug_event_pairs_drug_name", "drug_name_normalized"),
        Index("ix_drug_event_pairs_event_term", "event_term_normalized"),
    )


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
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_signal_results_drug_name", "drug_name"),
    )
