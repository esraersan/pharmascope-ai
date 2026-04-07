"""Unit tests for PRR and ROR signal detection."""

import pytest
from pharmascope.signals.calculator import compute_prr, compute_ror, SignalScore


def test_prr_known_signal():
    """PRR should be high when drug-event co-occurrence is elevated."""
    # a=50 (drug+event), b=10 (other drugs+event)
    # c=50 (drug+other events), d=890 (other drugs+other events)
    prr, lower, upper = compute_prr(50, 10, 50, 890)
    assert prr > 2.0, "Strong signal should have PRR > 2.0"
    assert lower > 1.0, "Lower CI should be above 1.0 for real signal"
    assert upper > prr, "Upper CI should be above PRR"


def test_prr_no_signal():
    """PRR should be near 1.0 when drug-event is not elevated."""
    prr, lower, upper = compute_prr(10, 100, 90, 900)
    assert prr < 2.0, "No signal should have PRR < 2.0"


def test_ror_known_signal():
    """ROR should be high for a strong signal."""
    ror, lower, upper = compute_ror(50, 10, 50, 890)
    assert ror > 2.0
    assert lower > 1.0


def test_ror_no_signal():
    """ROR should be near 1.0 for no signal."""
    ror, lower, upper = compute_ror(10, 100, 90, 900)
    assert ror < 2.0


def test_prr_zero_counts():
    """PRR should handle zero counts without crashing (Haldane correction)."""
    prr, lower, upper = compute_prr(0, 0, 0, 0)
    assert prr is not None
    assert not (prr != prr)  # not NaN


def test_signal_score_is_signal():
    """SignalScore.is_signal should flag strong signals correctly."""
    score = SignalScore(
        drug_name="rofecoxib",
        event_term="myocardial infarction",
        report_count=10,
        prr=3.5,
        prr_lower_ci=2.1,
        prr_upper_ci=5.8,
        ror=4.0,
        ror_lower_ci=2.5,
        ror_upper_ci=6.4,
    )
    assert score.is_signal is True


def test_signal_score_not_signal_low_count():
    """SignalScore.is_signal should not flag when count is too low."""
    score = SignalScore(
        drug_name="rofecoxib",
        event_term="headache",
        report_count=2,
        prr=3.5,
        prr_lower_ci=2.1,
        prr_upper_ci=5.8,
        ror=4.0,
        ror_lower_ci=2.5,
        ror_upper_ci=6.4,
    )
    assert score.is_signal is False


def test_signal_score_not_signal_low_prr():
    """SignalScore.is_signal should not flag when PRR is below threshold."""
    score = SignalScore(
        drug_name="rofecoxib",
        event_term="nausea",
        report_count=10,
        prr=1.5,
        prr_lower_ci=0.9,
        prr_upper_ci=2.1,
        ror=1.6,
        ror_lower_ci=0.95,
        ror_upper_ci=2.3,
    )
    assert score.is_signal is False
