"""
Statistical signal detection for drug-event pairs.

Implements Proportional Reporting Ratio (PRR) and 
Reporting Odds Ratio (ROR) — standard pharmacovigilance methods.
"""

from dataclasses import dataclass

import numpy as np
import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from pharmascope.ingestion.models import DataSnapshot

logger = structlog.get_logger()


@dataclass
class SignalScore:
    """Signal detection result for a single drug-event pair."""
    drug_name: str
    event_term: str
    report_count: int
    prr: float
    prr_lower_ci: float
    prr_upper_ci: float
    ror: float
    ror_lower_ci: float
    ror_upper_ci: float
    snapshot_id: str = ""

    @property
    def is_signal(self) -> bool:
        """
        A signal is flagged if:
        - At least 3 reports
        - PRR >= 2.0
        - Lower CI of PRR > 1.0
        """
        return (
            self.report_count >= 3
            and self.prr >= 2.0
            and self.prr_lower_ci > 1.0
        )


def compute_prr(a: int, b: int, c: int, d: int) -> tuple[float, float, float]:
    """
    Compute Proportional Reporting Ratio with 95% confidence interval.

    The 2x2 contingency table:
                    Drug X    All other drugs
    Event Y           a            b
    All other events  c            d

    PRR = (a / (a+c)) / (b / (b+d))

    Args:
        a: Reports with drug X AND event Y
        b: Reports with other drugs AND event Y  
        c: Reports with drug X AND other events
        d: Reports with other drugs AND other events

    Returns:
        Tuple of (prr, lower_ci, upper_ci)
    """
    # Add 0.5 to avoid division by zero (Haldane correction)
    a, b, c, d = a + 0.5, b + 0.5, c + 0.5, d + 0.5

    prr = (a / (a + c)) / (b / (b + d))

    # Log scale confidence interval
    log_prr = np.log(prr)
    se = np.sqrt(1/a - 1/(a+c) + 1/b - 1/(b+d))
    lower = np.exp(log_prr - 1.96 * se)
    upper = np.exp(log_prr + 1.96 * se)

    return float(round(prr, 4)), float(round(lower, 4)), float(round(upper, 4))


def compute_ror(a: int, b: int, c: int, d: int) -> tuple[float, float, float]:
    """
    Compute Reporting Odds Ratio with 95% confidence interval.

    ROR = (a/c) / (b/d) = (a*d) / (b*c)

    Args:
        a: Reports with drug X AND event Y
        b: Reports with other drugs AND event Y
        c: Reports with drug X AND other events
        d: Reports with other drugs AND other events

    Returns:
        Tuple of (ror, lower_ci, upper_ci)
    """
    a, b, c, d = a + 0.5, b + 0.5, c + 0.5, d + 0.5

    ror = (a * d) / (b * c)

    log_ror = np.log(ror)
    se = np.sqrt(1/a + 1/b + 1/c + 1/d)
    lower = np.exp(log_ror - 1.96 * se)
    upper = np.exp(log_ror + 1.96 * se)

    return float(round(ror, 4)), float(round(lower, 4)), float(round(upper, 4))


def get_contingency_table(
    drug_name: str,
    event_term: str,
    db: Session,
    snapshot_id: str,
) -> tuple[int, int, int, int]:
    """
    Build the 2x2 contingency table for a drug-event pair.

    Returns:
        Tuple of (a, b, c, d)
    """
    params = {
        "drug": drug_name,
        "event": event_term,
        "snapshot_id": snapshot_id,
    }

    # a: this drug + this event
    a = db.execute(text("""
        SELECT COUNT(DISTINCT report_id) FROM drug_event_pairs
        WHERE snapshot_id = :snapshot_id
        AND drug_name_normalized = :drug
        AND event_term_normalized = :event
        AND drug_role IN ('primary_suspect', 'secondary_suspect')
    """), params).scalar()

    # a+c: this drug, all events
    ac = db.execute(text("""
        SELECT COUNT(DISTINCT report_id) FROM drug_event_pairs
        WHERE snapshot_id = :snapshot_id
        AND drug_name_normalized = :drug
        AND drug_role IN ('primary_suspect', 'secondary_suspect')
    """), params).scalar()

    # a+b: all drugs, this event
    ab = db.execute(text("""
        SELECT COUNT(DISTINCT report_id) FROM drug_event_pairs
        WHERE snapshot_id = :snapshot_id
        AND event_term_normalized = :event
        AND drug_role IN ('primary_suspect', 'secondary_suspect')
    """), params).scalar()

    # total reports
    total = db.execute(text("""
        SELECT COUNT(DISTINCT report_id) FROM drug_event_pairs
        WHERE snapshot_id = :snapshot_id
        AND drug_role IN ('primary_suspect', 'secondary_suspect')
    """), params).scalar()

    c = ac - a
    b = ab - a
    d = total - a - b - c

    return int(a), int(b), int(c), int(d)


def resolve_snapshot_id(db: Session, snapshot_id: str | None = None) -> str:
    """Return a complete immutable snapshot or fail with an actionable error."""
    query = db.query(DataSnapshot).filter_by(is_complete=True)
    if snapshot_id:
        snapshot = query.filter_by(snapshot_id=snapshot_id).first()
    else:
        snapshot = query.order_by(DataSnapshot.period_end.desc()).first()
    if snapshot is None:
        requested = f" '{snapshot_id}'" if snapshot_id else ""
        raise ValueError(
            f"No complete FAERS snapshot{requested} is available. "
            "Import and validate a fixed snapshot before computing signals."
        )
    return snapshot.snapshot_id


def compute_signals(
    drug_name: str,
    db: Session,
    snapshot_id: str | None = None,
) -> list[SignalScore]:
    """
    Compute PRR and ROR signals for all events associated with a drug.

    Args:
        drug_name: Normalized drug name e.g. 'rofecoxib'
        db: Database session

    Returns:
        List of SignalScore objects sorted by PRR descending
    """
    snapshot_id = resolve_snapshot_id(db, snapshot_id)
    logger.info("computing_signals", drug=drug_name, snapshot_id=snapshot_id)

    # Get all events for this drug with their counts
    rows = db.execute(text("""
        SELECT event_term_normalized, COUNT(DISTINCT report_id) as cnt
        FROM drug_event_pairs
        WHERE snapshot_id = :snapshot_id
        AND drug_name_normalized = :drug
        AND drug_role IN ('primary_suspect', 'secondary_suspect')
        GROUP BY event_term_normalized
        HAVING COUNT(DISTINCT report_id) >= 3
        ORDER BY cnt DESC
    """), {"drug": drug_name, "snapshot_id": snapshot_id}).fetchall()

    scores = []
    for row in rows:
        event_term = row[0]
        report_count = row[1]

        a, b, c, d = get_contingency_table(
            drug_name,
            event_term,
            db,
            snapshot_id,
        )

        prr, prr_lower, prr_upper = compute_prr(a, b, c, d)
        ror, ror_lower, ror_upper = compute_ror(a, b, c, d)

        score = SignalScore(
            drug_name=drug_name,
            event_term=event_term,
            report_count=report_count,
            prr=prr,
            prr_lower_ci=prr_lower,
            prr_upper_ci=prr_upper,
            ror=ror,
            ror_lower_ci=ror_lower,
            ror_upper_ci=ror_upper,
            snapshot_id=snapshot_id,
        )
        scores.append(score)

    scores.sort(key=lambda x: x.prr, reverse=True)
    logger.info("signals_computed", drug=drug_name, count=len(scores))
    return scores
