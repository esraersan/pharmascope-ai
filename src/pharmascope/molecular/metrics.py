"""Binary classification metrics implemented with NumPy only."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Sequence

import numpy as np


def _validated_arrays(
    labels: Sequence[int], probabilities: Sequence[float]
) -> tuple[np.ndarray, np.ndarray]:
    y_true = np.asarray(labels)
    y_score = np.asarray(probabilities, dtype=float)
    if y_true.ndim != 1 or y_score.ndim != 1 or y_true.shape != y_score.shape:
        raise ValueError("labels and probabilities must be equal-length 1D arrays")
    if y_true.size == 0:
        raise ValueError("labels and probabilities must not be empty")
    if not np.all(np.isin(y_true, (0, 1))):
        raise ValueError("labels must be binary integers")
    if not np.all(np.isfinite(y_score)) or np.any((y_score < 0) | (y_score > 1)):
        raise ValueError("probabilities must be finite values in [0, 1]")
    return y_true.astype(np.int8), y_score


def roc_auc(labels: Sequence[int], probabilities: Sequence[float]) -> float:
    """Compute ROC-AUC with average ranks for tied scores."""

    y_true, y_score = _validated_arrays(labels, probabilities)
    positive_count = int(y_true.sum())
    negative_count = int(y_true.size - positive_count)
    if positive_count == 0 or negative_count == 0:
        raise ValueError("ROC-AUC requires both positive and negative labels")

    order = np.argsort(y_score, kind="mergesort")
    sorted_scores = y_score[order]
    ranks = np.empty(y_score.size, dtype=float)
    start = 0
    while start < y_score.size:
        end = start + 1
        while end < y_score.size and sorted_scores[end] == sorted_scores[start]:
            end += 1
        ranks[order[start:end]] = (start + 1 + end) / 2.0
        start = end

    positive_rank_sum = float(ranks[y_true == 1].sum())
    return (
        positive_rank_sum - positive_count * (positive_count + 1) / 2
    ) / (positive_count * negative_count)


def brier_score(labels: Sequence[int], probabilities: Sequence[float]) -> float:
    """Return mean squared probability error."""

    y_true, y_score = _validated_arrays(labels, probabilities)
    return float(np.mean((y_score - y_true) ** 2))


@dataclass(frozen=True, slots=True)
class CalibrationBin:
    lower: float
    upper: float
    count: int
    mean_probability: float
    observed_rate: float


def calibration_curve(
    labels: Sequence[int],
    probabilities: Sequence[float],
    *,
    n_bins: int = 10,
) -> tuple[CalibrationBin, ...]:
    """Return equal-width calibration bins, omitting empty bins."""

    y_true, y_score = _validated_arrays(labels, probabilities)
    if n_bins <= 0:
        raise ValueError("n_bins must be positive")
    bin_indices = np.minimum((y_score * n_bins).astype(int), n_bins - 1)
    bins: list[CalibrationBin] = []
    for index in range(n_bins):
        mask = bin_indices == index
        count = int(mask.sum())
        if count == 0:
            continue
        bins.append(
            CalibrationBin(
                lower=index / n_bins,
                upper=(index + 1) / n_bins,
                count=count,
                mean_probability=float(y_score[mask].mean()),
                observed_rate=float(y_true[mask].mean()),
            )
        )
    return tuple(bins)


@dataclass(frozen=True, slots=True)
class BinaryMetrics:
    n_samples: int
    prevalence: float
    roc_auc: float
    brier_score: float
    expected_calibration_error: float
    calibration: tuple[CalibrationBin, ...]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def binary_metrics(
    labels: Sequence[int],
    probabilities: Sequence[float],
    *,
    n_bins: int = 10,
) -> BinaryMetrics:
    """Compute discrimination and calibration metrics together."""

    y_true, y_score = _validated_arrays(labels, probabilities)
    bins = calibration_curve(y_true, y_score, n_bins=n_bins)
    expected_calibration_error = sum(
        item.count
        / y_true.size
        * abs(item.mean_probability - item.observed_rate)
        for item in bins
    )
    return BinaryMetrics(
        n_samples=int(y_true.size),
        prevalence=float(y_true.mean()),
        roc_auc=roc_auc(y_true, y_score),
        brier_score=brier_score(y_true, y_score),
        expected_calibration_error=float(expected_calibration_error),
        calibration=bins,
    )
