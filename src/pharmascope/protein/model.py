"""NumPy ridge-regression baseline for protein-ligand features."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np
from numpy.typing import ArrayLike, NDArray


def _matrix(value: ArrayLike, name: str) -> NDArray[np.float64]:
    array = np.asarray(value, dtype=float)
    if array.ndim != 2 or array.shape[0] == 0 or array.shape[1] == 0:
        raise ValueError(f"{name} must be a non-empty 2D array")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    return array


@dataclass(frozen=True)
class RidgeRegressor:
    """Fitted ridge model with training-set feature standardization."""

    coefficients: NDArray[np.float64]
    intercept: float
    feature_mean: NDArray[np.float64]
    feature_scale: NDArray[np.float64]
    alpha: float

    def predict(self, features: ArrayLike) -> NDArray[np.float64]:
        """Predict continuous targets."""

        matrix = np.asarray(features, dtype=float)
        if matrix.ndim != 2 or matrix.shape[1] != self.coefficients.size:
            raise ValueError(
                f"features must have shape (n, {self.coefficients.size})"
            )
        if not np.isfinite(matrix).all():
            raise ValueError("features must contain only finite values")
        standardized = (matrix - self.feature_mean) / self.feature_scale
        return standardized @ self.coefficients + self.intercept

    def to_dict(self) -> dict[str, Any]:
        """Serialize model parameters to JSON-compatible values."""

        return {
            "model_type": "ridge_regression",
            "alpha": self.alpha,
            "intercept": self.intercept,
            "coefficients": self.coefficients.tolist(),
            "feature_mean": self.feature_mean.tolist(),
            "feature_scale": self.feature_scale.tolist(),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> RidgeRegressor:
        """Restore and validate serialized model parameters."""

        if value.get("model_type") != "ridge_regression":
            raise ValueError("unsupported model_type")
        coefficients = np.asarray(value["coefficients"], dtype=float)
        feature_mean = np.asarray(value["feature_mean"], dtype=float)
        feature_scale = np.asarray(value["feature_scale"], dtype=float)
        if (
            coefficients.ndim != 1
            or feature_mean.shape != coefficients.shape
            or feature_scale.shape != coefficients.shape
            or not np.isfinite(coefficients).all()
            or not np.isfinite(feature_mean).all()
            or not np.isfinite(feature_scale).all()
            or np.any(feature_scale <= 0)
        ):
            raise ValueError("serialized model arrays are invalid")
        alpha = float(value["alpha"])
        intercept = float(value["intercept"])
        if alpha < 0 or not np.isfinite([alpha, intercept]).all():
            raise ValueError("serialized model scalars are invalid")
        return cls(coefficients, intercept, feature_mean, feature_scale, alpha)


def fit_ridge(
    features: ArrayLike, targets: ArrayLike, *, alpha: float = 1.0
) -> RidgeRegressor:
    """Fit ridge regression, leaving the centered intercept unregularized."""

    matrix = _matrix(features, "features")
    target = np.asarray(targets, dtype=float)
    if target.ndim != 1 or target.shape[0] != matrix.shape[0]:
        raise ValueError("targets must be 1D with one value per feature row")
    if not np.isfinite(target).all():
        raise ValueError("targets must contain only finite values")
    if not np.isfinite(alpha) or alpha < 0:
        raise ValueError("alpha must be a finite non-negative number")

    mean = matrix.mean(axis=0)
    scale = matrix.std(axis=0)
    scale[scale == 0] = 1.0
    standardized = (matrix - mean) / scale
    centered_target = target - target.mean()
    system = standardized.T @ standardized
    system.flat[:: system.shape[0] + 1] += alpha
    right_hand_side = standardized.T @ centered_target
    try:
        coefficients = np.linalg.solve(system, right_hand_side)
    except np.linalg.LinAlgError:
        coefficients = np.linalg.lstsq(system, right_hand_side, rcond=None)[0]

    return RidgeRegressor(
        coefficients=coefficients,
        intercept=float(target.mean()),
        feature_mean=mean,
        feature_scale=scale,
        alpha=float(alpha),
    )
