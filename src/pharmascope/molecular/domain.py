"""Applicability-domain and error-analysis helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Sequence

import numpy as np

from .fingerprints import tanimoto_similarity
from .records import SmilesRecord


@dataclass(frozen=True, slots=True)
class ApplicabilityAssessment:
    nearest_similarity: np.ndarray
    nearest_training_index: np.ndarray
    in_domain: np.ndarray
    similarity_threshold: float
    method: str = "nearest_lexical_fingerprint_tanimoto"


def assess_applicability(
    training_fingerprints: np.ndarray,
    query_fingerprints: np.ndarray,
    *,
    similarity_threshold: float = 0.3,
) -> ApplicabilityAssessment:
    """Assess queries by nearest lexical-fingerprint Tanimoto similarity."""

    training = np.asarray(training_fingerprints)
    queries = np.asarray(query_fingerprints)
    if training.ndim != 2 or queries.ndim != 2:
        raise ValueError("fingerprint matrices must be two-dimensional")
    if training.shape[0] == 0:
        raise ValueError("at least one training fingerprint is required")
    if training.shape[1] != queries.shape[1]:
        raise ValueError("training and query fingerprints must have equal width")
    if not 0 <= similarity_threshold <= 1:
        raise ValueError("similarity_threshold must be in [0, 1]")

    nearest_similarity = np.empty(queries.shape[0], dtype=float)
    nearest_index = np.empty(queries.shape[0], dtype=int)
    for query_index, query in enumerate(queries):
        similarities = np.array(
            [tanimoto_similarity(query, candidate) for candidate in training]
        )
        nearest_index[query_index] = int(np.argmax(similarities))
        nearest_similarity[query_index] = float(
            similarities[nearest_index[query_index]]
        )
    return ApplicabilityAssessment(
        nearest_similarity=nearest_similarity,
        nearest_training_index=nearest_index,
        in_domain=nearest_similarity >= similarity_threshold,
        similarity_threshold=similarity_threshold,
    )


@dataclass(frozen=True, slots=True)
class ErrorCase:
    index: int
    compound_id: str
    smiles: str
    label: int
    probability: float
    predicted_label: int
    absolute_error: float
    nearest_similarity: float | None = None


@dataclass(frozen=True, slots=True)
class ErrorAnalysis:
    threshold: float
    true_positive: int
    true_negative: int
    false_positive: int
    false_negative: int
    cases: tuple[ErrorCase, ...]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def error_analysis(
    records: Sequence[SmilesRecord],
    probabilities: Sequence[float],
    *,
    threshold: float = 0.5,
    nearest_similarities: Sequence[float] | None = None,
) -> ErrorAnalysis:
    """Summarize confusion counts and rank observations by probability error."""

    scores = np.asarray(probabilities, dtype=float)
    if len(records) != scores.size or scores.ndim != 1:
        raise ValueError("records and probabilities must have equal lengths")
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be in [0, 1]")
    if not np.all(np.isfinite(scores)) or np.any((scores < 0) | (scores > 1)):
        raise ValueError("probabilities must be finite values in [0, 1]")
    similarities: np.ndarray | None = None
    if nearest_similarities is not None:
        similarities = np.asarray(nearest_similarities, dtype=float)
        if similarities.shape != scores.shape:
            raise ValueError("nearest_similarities must align with records")
        if not np.all(np.isfinite(similarities)) or np.any(
            (similarities < 0) | (similarities > 1)
        ):
            raise ValueError("nearest similarities must be in [0, 1]")

    labels = np.array([record.label for record in records], dtype=int)
    predictions = (scores >= threshold).astype(int)
    cases = tuple(
        sorted(
            (
                ErrorCase(
                    index=index,
                    compound_id=record.compound_id,
                    smiles=record.smiles,
                    label=record.label,
                    probability=float(scores[index]),
                    predicted_label=int(predictions[index]),
                    absolute_error=float(abs(scores[index] - record.label)),
                    nearest_similarity=(
                        None if similarities is None else float(similarities[index])
                    ),
                )
                for index, record in enumerate(records)
            ),
            key=lambda item: (-item.absolute_error, item.index),
        )
    )
    return ErrorAnalysis(
        threshold=threshold,
        true_positive=int(np.sum((labels == 1) & (predictions == 1))),
        true_negative=int(np.sum((labels == 0) & (predictions == 0))),
        false_positive=int(np.sum((labels == 0) & (predictions == 1))),
        false_negative=int(np.sum((labels == 1) & (predictions == 0))),
        cases=cases,
    )
