"""Transparent sequence-composition and hashed ligand baseline features."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Sequence

import numpy as np
from numpy.typing import NDArray

from .schema import ProteinLigandRecord

AMINO_ACIDS = "ACDEFGHIKLMNPQRSTVWY"


@dataclass(frozen=True)
class FeatureConfig:
    """Configuration for deterministic baseline features."""

    ligand_hash_size: int = 256
    ligand_ngram_min: int = 2
    ligand_ngram_max: int = 4
    signed_hashing: bool = True

    def __post_init__(self) -> None:
        if self.ligand_hash_size < 1:
            raise ValueError("ligand_hash_size must be positive")
        if self.ligand_ngram_min < 1:
            raise ValueError("ligand_ngram_min must be positive")
        if self.ligand_ngram_max < self.ligand_ngram_min:
            raise ValueError("ligand_ngram_max must be >= ligand_ngram_min")

    def to_dict(self) -> dict[str, int | bool]:
        return asdict(self)


def _sequence_features(sequence: str) -> NDArray[np.float64]:
    length = len(sequence)
    counts = np.array([sequence.count(residue) for residue in AMINO_ACIDS], dtype=float)
    canonical_count = float(counts.sum())
    return np.concatenate(
        (
            counts / length,
            np.array(
                [
                    np.log1p(length),
                    (length - canonical_count) / length,
                ],
                dtype=float,
            ),
        )
    )


def _ligand_features(
    representation: str, config: FeatureConfig
) -> NDArray[np.float64]:
    vector = np.zeros(config.ligand_hash_size, dtype=float)
    bounded = f"^{representation}$"
    for size in range(config.ligand_ngram_min, config.ligand_ngram_max + 1):
        for start in range(max(0, len(bounded) - size + 1)):
            token = bounded[start : start + size].encode("utf-8")
            digest = hashlib.blake2b(token, digest_size=16).digest()
            bucket_hash = int.from_bytes(digest[:8], "big")
            sign_hash = int.from_bytes(digest[8:], "big")
            index = bucket_hash % config.ligand_hash_size
            sign = -1.0 if config.signed_hashing and sign_hash & 1 else 1.0
            vector[index] += sign
    norm = np.linalg.norm(vector)
    if norm:
        vector /= norm
    return vector


def featurize_records(
    records: Sequence[ProteinLigandRecord],
    config: FeatureConfig | None = None,
) -> NDArray[np.float64]:
    """Create a deterministic matrix without learned or pretrained embeddings."""

    config = config or FeatureConfig()
    width = len(AMINO_ACIDS) + 2 + config.ligand_hash_size
    if not records:
        return np.empty((0, width), dtype=float)
    rows = [
        np.concatenate(
            (
                _sequence_features(record.protein_sequence),
                _ligand_features(record.ligand_representation, config),
            )
        )
        for record in records
    ]
    return np.vstack(rows)


def feature_names(config: FeatureConfig | None = None) -> tuple[str, ...]:
    """Return stable labels corresponding to columns from ``featurize_records``."""

    config = config or FeatureConfig()
    sequence = tuple(f"protein_fraction_{residue}" for residue in AMINO_ACIDS)
    ligand = tuple(f"ligand_hash_{index}" for index in range(config.ligand_hash_size))
    return sequence + ("protein_log_length", "protein_ambiguous_fraction") + ligand
