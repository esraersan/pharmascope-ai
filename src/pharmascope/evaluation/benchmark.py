"""Reproducible temporal evaluation for FAERS signal detection."""

from __future__ import annotations

import calendar
import csv
import json
import math
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from pharmascope.signals.calculator import compute_prr, compute_ror

SUSPECT_ROLES = {"primary_suspect", "secondary_suspect"}


@dataclass(frozen=True)
class PairObservation:
    """One normalized report-level drug/event observation."""

    report_id: str
    receive_date: date
    drug_name: str
    event_term: str
    drug_role: str


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    drug_name: str
    event_term: str
    expected_signal: bool
    regulatory_date: date | None
    source_url: str
    notes: str


@dataclass(frozen=True)
class TemporalPoint:
    cutoff: date
    a: int
    b: int
    c: int
    d: int
    prr: float
    prr_lower_ci: float
    prr_upper_ci: float
    ror: float
    information_component: float
    is_signal: bool


def load_observations(path: Path) -> list[PairObservation]:
    """Load the documented normalized CSV interchange format."""
    observations: list[PairObservation] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            observations.append(
                PairObservation(
                    report_id=row["report_id"],
                    receive_date=date.fromisoformat(row["receive_date"][:10]),
                    drug_name=row["drug_name_normalized"].strip().lower(),
                    event_term=row["event_term_normalized"].strip().lower(),
                    drug_role=row["drug_role"].strip().lower(),
                )
            )
    return observations


def load_cases(path: Path) -> list[BenchmarkCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        BenchmarkCase(
            **{
                **item,
                "regulatory_date": (
                    date.fromisoformat(item["regulatory_date"])
                    if item.get("regulatory_date")
                    else None
                ),
            }
        )
        for item in payload["cases"]
    ]


def contingency_from_observations(
    observations: list[PairObservation],
    *,
    drug_name: str,
    event_term: str,
    cutoff: date,
) -> tuple[int, int, int, int]:
    """Build report-level counts from a fixed snapshot up to one cutoff."""
    eligible = [
        row
        for row in observations
        if row.receive_date <= cutoff and row.drug_role in SUSPECT_ROLES
    ]
    all_reports = {row.report_id for row in eligible}
    drug_reports = {
        row.report_id for row in eligible if row.drug_name == drug_name
    }
    event_reports = {
        row.report_id for row in eligible if row.event_term == event_term
    }
    joint_reports = drug_reports & event_reports
    a = len(joint_reports)
    b = len(event_reports - drug_reports)
    c = len(drug_reports - event_reports)
    d = len(all_reports - drug_reports - event_reports)
    return a, b, c, d


def information_component(a: int, b: int, c: int, d: int) -> float:
    """Compute a smoothed log2 observed-to-expected reporting ratio.

    This transparent comparator is IC-like but is not a reimplementation of
    WHO-UMC BCPNN credibility intervals.
    """
    total = a + b + c + d
    observed = a + 0.5
    expected = ((a + c + 1.0) * (a + b + 1.0)) / (total + 2.0)
    return round(math.log2(observed / expected), 4)


def temporal_trajectory(
    observations: list[PairObservation],
    case: BenchmarkCase,
    cutoffs: list[date],
) -> list[TemporalPoint]:
    points: list[TemporalPoint] = []
    for cutoff in sorted(set(cutoffs)):
        a, b, c, d = contingency_from_observations(
            observations,
            drug_name=case.drug_name,
            event_term=case.event_term,
            cutoff=cutoff,
        )
        prr, lower, upper = compute_prr(a, b, c, d)
        ror, _, _ = compute_ror(a, b, c, d)
        points.append(
            TemporalPoint(
                cutoff=cutoff,
                a=a,
                b=b,
                c=c,
                d=d,
                prr=prr,
                prr_lower_ci=lower,
                prr_upper_ci=upper,
                ror=ror,
                information_component=information_component(a, b, c, d),
                is_signal=a >= 3 and prr >= 2 and lower > 1,
            )
        )
    return points


def first_signal_date(points: list[TemporalPoint]) -> date | None:
    return next((point.cutoff for point in points if point.is_signal), None)


def monthly_cutoffs(start: date, stop: date) -> list[date]:
    """Return month-end cutoffs spanning an inclusive date range."""
    year, month = start.year, start.month
    cutoffs: list[date] = []
    while (year, month) <= (stop.year, stop.month):
        cutoffs.append(date(year, month, calendar.monthrange(year, month)[1]))
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return cutoffs


def classification_metrics(
    expected: list[bool],
    predicted: list[bool],
) -> dict[str, float | int]:
    if len(expected) != len(predicted) or not expected:
        raise ValueError(
            "Expected and predicted labels must have equal non-zero length"
        )
    tp = sum(want and got for want, got in zip(expected, predicted, strict=True))
    fp = sum(not want and got for want, got in zip(expected, predicted, strict=True))
    tn = sum(
        not want and not got
        for want, got in zip(expected, predicted, strict=True)
    )
    fn = sum(want and not got for want, got in zip(expected, predicted, strict=True))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
    }


def write_trajectory(path: Path, points: list[TemporalPoint]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            [
                {
                    **asdict(point),
                    "cutoff": point.cutoff.isoformat(),
                }
                for point in points
            ],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def run_benchmark(
    observations: list[PairObservation],
    cases: list[BenchmarkCase],
    output_dir: Path,
) -> dict:
    """Run all cases over the snapshot's observed time range."""
    if not observations:
        raise ValueError("The benchmark requires at least one observation")
    cutoffs = monthly_cutoffs(
        min(row.receive_date for row in observations),
        max(row.receive_date for row in observations),
    )
    predictions: list[bool] = []
    summary_cases: list[dict] = []
    for case in cases:
        points = temporal_trajectory(observations, case, cutoffs)
        signal_date = first_signal_date(points)
        predictions.append(signal_date is not None)
        lead_time_days = (
            (case.regulatory_date - signal_date).days
            if signal_date and case.regulatory_date
            else None
        )
        write_trajectory(output_dir / f"{case.case_id}.json", points)
        summary_cases.append(
            {
                "case_id": case.case_id,
                "expected_signal": case.expected_signal,
                "first_signal_date": signal_date.isoformat() if signal_date else None,
                "regulatory_date": (
                    case.regulatory_date.isoformat()
                    if case.regulatory_date
                    else None
                ),
                "lead_time_days": lead_time_days,
                "source_url": case.source_url,
            }
        )

    summary = {
        "observation_count": len(observations),
        "report_count": len({row.report_id for row in observations}),
        "period_start": min(row.receive_date for row in observations).isoformat(),
        "period_end": max(row.receive_date for row in observations).isoformat(),
        "metrics": classification_metrics(
            [case.expected_signal for case in cases],
            predictions,
        ),
        "cases": summary_cases,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary
