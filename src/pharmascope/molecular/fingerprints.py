"""Deterministic lexical SMILES fingerprints.

These features hash SMILES token n-grams. They are useful as a reproducible,
low-dependency baseline, but they are not molecular graph fingerprints.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

import numpy as np

_TOKEN_PATTERN = re.compile(
    r"(\[[^\]]+\]|Br|Cl|Si|Se|Na|Li|Ca|Mg|Al|[A-Z][a-z]?|"
    r"[bcnops]|\%\d{2}|\d|[-=#:/.\\()]|\+)"
)


def tokenize_smiles(smiles: str) -> tuple[str, ...]:
    """Tokenize SMILES text and reject characters the lexer cannot represent."""

    if not isinstance(smiles, str) or not smiles:
        raise ValueError("smiles must be a non-empty string")
    tokens: list[str] = []
    cursor = 0
    for match in _TOKEN_PATTERN.finditer(smiles):
        if match.start() != cursor:
            raise ValueError(
                f"unsupported SMILES text at character {cursor}: {smiles[cursor]!r}"
            )
        tokens.append(match.group(0))
        cursor = match.end()
    if cursor != len(smiles):
        raise ValueError(
            f"unsupported SMILES text at character {cursor}: {smiles[cursor]!r}"
        )
    return tuple(tokens)


def hashed_token_fingerprint(
    smiles: str,
    *,
    n_bits: int = 2048,
    ngram_range: tuple[int, int] = (1, 3),
) -> np.ndarray:
    """Create a binary fingerprint from stable hashes of token n-grams."""

    if n_bits <= 0:
        raise ValueError("n_bits must be positive")
    minimum, maximum = ngram_range
    if minimum <= 0 or maximum < minimum:
        raise ValueError("ngram_range must contain positive increasing values")

    tokens = tokenize_smiles(smiles)
    fingerprint = np.zeros(n_bits, dtype=np.uint8)
    for size in range(minimum, maximum + 1):
        for start in range(len(tokens) - size + 1):
            feature = "\x1f".join(tokens[start : start + size]).encode("utf-8")
            digest = hashlib.blake2b(feature, digest_size=8).digest()
            bit = int.from_bytes(digest, "big") % n_bits
            fingerprint[bit] = 1
    return fingerprint


def fingerprint_matrix(
    smiles_values: Iterable[str],
    *,
    n_bits: int = 2048,
    ngram_range: tuple[int, int] = (1, 3),
) -> np.ndarray:
    """Fingerprint a sequence into a two-dimensional uint8 array."""

    rows = [
        hashed_token_fingerprint(
            smiles, n_bits=n_bits, ngram_range=ngram_range
        )
        for smiles in smiles_values
    ]
    if not rows:
        return np.empty((0, n_bits), dtype=np.uint8)
    return np.vstack(rows)


def tanimoto_similarity(left: np.ndarray, right: np.ndarray) -> float:
    """Compute Tanimoto similarity for two binary feature vectors."""

    left_array = np.asarray(left)
    right_array = np.asarray(right)
    if left_array.ndim != 1 or left_array.shape != right_array.shape:
        raise ValueError("fingerprints must be one-dimensional and equally sized")
    if not np.all(np.isin(left_array, (0, 1))) or not np.all(
        np.isin(right_array, (0, 1))
    ):
        raise ValueError("fingerprints must be binary")
    left_binary = left_array.astype(bool, copy=False)
    right_binary = right_array.astype(bool, copy=False)
    intersection = int(np.count_nonzero(left_binary & right_binary))
    union = int(np.count_nonzero(left_binary | right_binary))
    return 1.0 if union == 0 else intersection / union
