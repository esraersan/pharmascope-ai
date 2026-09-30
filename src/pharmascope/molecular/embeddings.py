"""Validated integration for externally generated molecular embeddings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np

from .records import SmilesRecord


@dataclass(frozen=True, slots=True)
class EmbeddingProvenance:
    """Identity and version information for a pretrained representation."""

    model_name: str
    model_revision: str
    pooling: str

    def __post_init__(self) -> None:
        for name in ("model_name", "model_revision", "pooling"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must be non-empty")


def embedding_matrix(
    records: Sequence[SmilesRecord],
    embeddings: Mapping[str, Sequence[float]],
) -> np.ndarray:
    """Align precomputed embeddings to records and reject silent omissions."""
    missing = [
        record.compound_id
        for record in records
        if record.compound_id not in embeddings
    ]
    if missing:
        raise ValueError(
            "Missing pretrained embeddings for compound IDs: "
            + ", ".join(sorted(missing))
        )
    rows = [
        np.asarray(embeddings[record.compound_id], dtype=float)
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
