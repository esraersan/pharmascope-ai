"""Tests for report-level temporal benchmark logic."""

from datetime import date
from pathlib import Path

from pharmascope.evaluation.benchmark import (
    BenchmarkCase,
    PairObservation,
    classification_metrics,
    contingency_from_observations,
    first_signal_date,
    load_cases,
    temporal_trajectory,
)


def _row(report_id: str, drug: str, event: str) -> PairObservation:
    return PairObservation(
        report_id=report_id,
        receive_date=date(2003, 1, 31),
        drug_name=drug,
        event_term=event,
        drug_role="primary_suspect",
    )


def test_contingency_counts_unique_reports():
    rows = [
        _row("a1", "drug-x", "event-y"),
        _row("a1", "drug-x", "event-y"),
        _row("b1", "other", "event-y"),
        _row("c1", "drug-x", "other-event"),
        _row("d1", "other", "other-event"),
    ]

    assert contingency_from_observations(
        rows,
        drug_name="drug-x",
        event_term="event-y",
        cutoff=date(2003, 12, 31),
    ) == (1, 1, 1, 1)


def test_temporal_signal_crossing_is_reproducible():
    rows = [
        *[_row(f"a{i}", "drug-x", "event-y") for i in range(10)],
        *[_row(f"b{i}", "other", "event-y") for i in range(2)],
        *[_row(f"c{i}", "drug-x", "other-event") for i in range(3)],
        *[_row(f"d{i}", "other", "other-event") for i in range(100)],
    ]
    case = BenchmarkCase(
        case_id="test",
        drug_name="drug-x",
        event_term="event-y",
        expected_signal=True,
        regulatory_date=date(2004, 1, 1),
        source_url="https://example.test",
        notes="Synthetic test only",
    )

    points = temporal_trajectory(rows, case, [date(2003, 12, 31)])

    assert points[0].is_signal
    assert first_signal_date(points) == date(2003, 12, 31)


def test_classification_metrics_reports_false_positives():
    metrics = classification_metrics(
        [True, True, False, False],
        [True, False, True, False],
    )

    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 0.5
    assert metrics["false_positives"] == 1


def test_curated_benchmark_has_sourced_cases_and_controls():
    cases = load_cases(Path("data/benchmark_cases.json"))

    assert sum(case.expected_signal for case in cases) >= 5
    assert sum(not case.expected_signal for case in cases) >= 5
    assert all(case.source_url.startswith("https://") for case in cases)
    assert all(
        case.regulatory_date is not None
        for case in cases
        if case.expected_signal
    )
