"""A small deterministic logistic-regression baseline for binary fingerprints."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


def _sigmoid(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(values, -35.0, 35.0)
    return 1.0 / (1.0 + np.exp(-clipped))


@dataclass(slots=True)
class FingerprintLogisticRegression:
    """Batch-gradient logistic regression with L2 weight regularization.

    This implementation is intended for transparent baselines, not as a
    feature-complete replacement for a mature optimization library.
    """

    learning_rate: float = 0.1
    max_iter: int = 500
    l2: float = 1e-3
    tolerance: float = 1e-8
    coefficients_: np.ndarray | None = field(default=None, init=False, repr=False)
    intercept_: float | None = field(default=None, init=False)
    n_iter_: int = field(default=0, init=False)

    def fit(
        self, features: np.ndarray, labels: np.ndarray
    ) -> "FingerprintLogisticRegression":
        """Fit model parameters and return this instance."""

        x, y = self._validate_training_data(features, labels)
        if self.learning_rate <= 0 or self.max_iter <= 0:
            raise ValueError("learning_rate and max_iter must be positive")
        if self.l2 < 0 or self.tolerance < 0:
            raise ValueError("l2 and tolerance must be non-negative")

        weights = np.zeros(x.shape[1], dtype=float)
        prevalence = float(np.clip(y.mean(), 1e-6, 1 - 1e-6))
        intercept = float(np.log(prevalence / (1 - prevalence)))

        for iteration in range(1, self.max_iter + 1):
            probabilities = _sigmoid(x @ weights + intercept)
            residual = probabilities - y
            weight_gradient = x.T @ residual / x.shape[0] + self.l2 * weights
            intercept_gradient = float(residual.mean())
            step_norm = float(
                np.linalg.norm(
                    np.append(weight_gradient, intercept_gradient)
                    * self.learning_rate
                )
            )
            weights -= self.learning_rate * weight_gradient
            intercept -= self.learning_rate * intercept_gradient
            self.n_iter_ = iteration
            if step_norm <= self.tolerance:
                break

        self.coefficients_ = weights
        self.intercept_ = intercept
        return self

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        """Return positive-class probabilities."""

        if self.coefficients_ is None or self.intercept_ is None:
            raise RuntimeError("model must be fitted before prediction")
        x = np.asarray(features, dtype=float)
        if x.ndim != 2 or x.shape[1] != self.coefficients_.size:
            raise ValueError("features have an incompatible shape")
        if not np.all(np.isfinite(x)):
            raise ValueError("features must be finite")
        return _sigmoid(x @ self.coefficients_ + self.intercept_)

    @staticmethod
    def _validate_training_data(
        features: np.ndarray, labels: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        x = np.asarray(features, dtype=float)
        y = np.asarray(labels)
        if x.ndim != 2 or y.ndim != 1 or x.shape[0] != y.size:
            raise ValueError("features must be 2D and align with 1D labels")
        if x.shape[0] == 0 or x.shape[1] == 0:
            raise ValueError("training data must not be empty")
        if not np.all(np.isfinite(x)):
            raise ValueError("features must be finite")
        if not np.all(np.isin(y, (0, 1))):
            raise ValueError("labels must be binary")
        if np.unique(y).size != 2:
            raise ValueError("training labels must contain both classes")
        return x, y.astype(float)
