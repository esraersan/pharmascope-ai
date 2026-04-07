"""
Statistical signal detection for drug-event pairs.

Implements Proportional Reporting Ratio (PRR) and 
Reporting Odds Ratio (ROR) — standard pharmacovigilance methods.
"""

import numpy as np
import structlog
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import text

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

    return round(prr, 4), round(lower, 4), round(upper, 4)


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

    return round(ror, 4), round(lower, 4), round(upper, 4)


def get_contingency_table(
    drug_name: str,
    event_term: str,
    db: Session
) -> tuple[int, int, int, int]:
    """
    Build the 2x2 contingency table for a drug-event pair.

    Returns:
        Tuple of (a, b, c, d)
    """
    # a: this drug + this event
    a = db.execute(text("""
        SELECT COUNT(DISTINCT report_id) FROM drug_event_pairs
        WHERE drug_name_normalized = :drug
        AND event_term_normalized = :event
    """), {"drug": drug_name, "event": event_term}).scalar()

    # a+c: this drug, all events
    ac = db.execute(text("""
        SELECT COUNT(DISTINCT report_id) FROM drug_event_pairs
        WHERE drug_name_normalized = :drug
    """), {"drug": drug_name}).scalar()

    # a+b: all drugs, this event
    ab = db.execute(text("""
        SELECT COUNT(DISTINCT report_id) FROM drug_event_pairs
        WHERE event_term_normalized = :event
    """), {"event": event_term}).scalar()

    # total reports
    total = db.execute(text("""
        SELECT COUNT(DISTINCT report_id) FROM drug_event_pairs
    """)).scalar()

    c = ac - a
    b = ab - a
    d = total - a - b - c

    return int(a), int(b), int(c), int(d)


def compute_signals(drug_name: str, db: Session) -> list[SignalScore]:
    """
    Compute PRR and ROR signals for all events associated with a drug.

    Args:
        drug_name: Normalized drug name e.g. 'rofecoxib'
        db: Database session

    Returns:
        List of SignalScore objects sorted by PRR descending
    """
    logger.info("computing_signals", drug=drug_name)

    # Get all events for this drug with their counts
    rows = db.execute(text("""
        SELECT event_term_normalized, COUNT(DISTINCT report_id) as cnt
        FROM drug_event_pairs
        WHERE drug_name_normalized = :drug
        GROUP BY event_term_normalized
        HAVING COUNT(DISTINCT report_id) >= 3
        ORDER BY cnt DESC
    """), {"drug": drug_name}).fetchall()

    scores = []
    for row in rows:
        event_term = row[0]
        report_count = row[1]

        a, b, c, d = get_contingency_table(drug_name, event_term, db)

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
        )
        scores.append(score)

    scores.sort(key=lambda x: x.prr, reverse=True)
    logger.info("signals_computed", drug=drug_name, count=len(scores))
    return scores
