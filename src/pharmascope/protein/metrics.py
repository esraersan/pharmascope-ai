"""Regression metrics with explicit handling of undefined R-squared."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from numpy.typing import ArrayLike


@dataclass(frozen=True)
class RegressionMetrics:
    count: int
    mean_absolute_error: float
    root_mean_squared_error: float
    r_squared: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def regression_metrics(actual: ArrayLike, predicted: ArrayLike) -> RegressionMetrics:
    """Compute MAE, RMSE, and R²; return ``None`` when R² is undefined."""

    observed = np.asarray(actual, dtype=float)
    estimates = np.asarray(predicted, dtype=float)
    if observed.ndim != 1 or estimates.ndim != 1:
        raise ValueError("actual and predicted must be 1D")
    if observed.shape != estimates.shape or observed.size == 0:
        raise ValueError("actual and predicted must have equal non-zero length")
    if not np.isfinite(observed).all() or not np.isfinite(estimates).all():
        raise ValueError("actual and predicted must contain only finite values")

    residual = estimates - observed
    mae = float(np.mean(np.abs(residual)))
    rmse = float(np.sqrt(np.mean(residual**2)))
    denominator = float(np.sum((observed - observed.mean()) ** 2))
    r_squared = (
        None
        if observed.size < 2 or denominator == 0.0
        else float(1.0 - np.sum(residual**2) / denominator)
    )
    return RegressionMetrics(
        count=int(observed.size),
        mean_absolute_error=mae,
        root_mean_squared_error=rmse,
        r_squared=r_squared,
    )
