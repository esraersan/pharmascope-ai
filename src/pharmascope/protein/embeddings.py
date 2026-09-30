"""Validated integration for precomputed protein language-model embeddings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
from numpy.typing import NDArray

from .schema import ProteinLigandRecord


@dataclass(frozen=True, slots=True)
class ProteinEmbeddingProvenance:
    """The exact pretrained representation used by an experiment."""

    model_name: str
    model_revision: str
    layer: str
    pooling: str

    def __post_init__(self) -> None:
        for name in ("model_name", "model_revision", "layer", "pooling"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must be non-empty")


def protein_embedding_matrix(
    records: Sequence[ProteinLigandRecord],
    embeddings: Mapping[str, Sequence[float]],
) -> NDArray[np.float64]:
    """Align one precomputed vector per protein without silent fallback."""
    missing = sorted(
        {
            record.protein_id
            for record in records
            if record.protein_id not in embeddings
        }
    )
    if missing:
        raise ValueError(
            "Missing pretrained embeddings for protein IDs: "
            + ", ".join(missing)
        )
    rows = [
        np.asarray(embeddings[record.protein_id], dtype=float)
        for record in records
    ]
    if not rows:
        return np.empty((0, 0), dtype=float)
    widths = {row.size for row in rows}
    if len(widths) != 1 or 0 in widths or any(row.ndim != 1 for row in rows):
        raise ValueError("Every embedding must be a non-empty 1D vector of equal width")
    matrix = np.vstack(rows)
    if not np.all(np.isfinite(matrix)):
        raise ValueError("Embeddings must contain only finite values")
    return matrix


def append_embeddings(
    baseline_features: NDArray[np.float64],
    pretrained_features: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Concatenate aligned baseline and pretrained feature matrices."""
    baseline = np.asarray(baseline_features, dtype=float)
    pretrained = np.asarray(pretrained_features, dtype=float)
    if baseline.ndim != 2 or pretrained.ndim != 2:
        raise ValueError("Both feature inputs must be two-dimensional")
    if baseline.shape[0] != pretrained.shape[0]:
        raise ValueError("Feature inputs must contain the same number of records")
    return np.concatenate((baseline, pretrained), axis=1)
