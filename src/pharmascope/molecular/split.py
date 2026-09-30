"""Deterministic grouped splitting based on lexical SMILES frameworks."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Sequence

from .fingerprints import tokenize_smiles
from .records import SmilesRecord

_BOND_TOKENS = frozenset({"-", "=", "#", ":", "/", "\\"})
_BRANCH_TOKENS = frozenset({"(", ")"})


def token_framework_key(smiles: str) -> str:
    """Return an approximate lexical framework key.

    The key retains atom, bond, branch, and ring-token order while reducing
    bracket atoms to their element-like token. It does not parse a graph,
    canonicalize SMILES, or compute a Bemis-Murcko scaffold. Equivalent
    molecules written as different SMILES may therefore receive different keys.
    """

    normalized: list[str] = []
    for token in tokenize_smiles(smiles):
        if token.startswith("["):
            body = token[1:-1]
            element = next(
                (
                    body[index : index + 2]
                    for index in range(len(body) - 1)
                    if body[index].isalpha()
                    and body[index + 1].islower()
                    and body[index : index + 2] in {"Cl", "Br", "Si", "Se"}
                ),
                None,
            )
            if element is None:
                element = next(
                    (character for character in body if character.isalpha()), "?"
                )
            normalized.append(element)
        elif token in _BOND_TOKENS or token in _BRANCH_TOKENS:
            normalized.append(token)
        else:
            normalized.append(token)
    return "".join(normalized)


@dataclass(frozen=True, slots=True)
class MolecularSplit:
    """Indices for a grouped train/validation/test partition."""

    train: tuple[int, ...]
    validation: tuple[int, ...]
    test: tuple[int, ...]
    method: str = "lexical_smiles_token_framework"

    def as_dict(self) -> dict[str, list[int] | str]:
        return {
            "train": list(self.train),
            "validation": list(self.validation),
            "test": list(self.test),
            "method": self.method,
        }


def deterministic_token_framework_split(
    records: Sequence[SmilesRecord],
    *,
    fractions: tuple[float, float, float] = (0.8, 0.1, 0.1),
    seed: int = 0,
) -> MolecularSplit:
    """Split records without allowing a lexical framework across partitions.

    Groups are ordered by size and a seeded stable hash, then greedily assigned
    to the partition with the largest remaining target deficit. This controls
    approximate partition sizes while preserving groups. It is not stratified
    and does not guarantee every partition or class is represented.
    """

    if len(fractions) != 3 or any(value < 0 for value in fractions):
        raise ValueError("fractions must contain three non-negative values")
    total_fraction = sum(fractions)
    if total_fraction <= 0:
        raise ValueError("at least one fraction must be positive")
    normalized_fractions = tuple(value / total_fraction for value in fractions)

    groups: dict[str, list[int]] = {}
    for index, record in enumerate(records):
        groups.setdefault(token_framework_key(record.smiles), []).append(index)

    def group_order(item: tuple[str, list[int]]) -> tuple[int, str]:
        key, indices = item
        digest = hashlib.sha256(f"{seed}\x1f{key}".encode()).hexdigest()
        return (-len(indices), digest)

    assignments: list[list[int]] = [[], [], []]
    targets = [len(records) * value for value in normalized_fractions]
    eligible_partitions = [
        position for position, value in enumerate(normalized_fractions) if value > 0
    ]
    for _, indices in sorted(groups.items(), key=group_order):
        deficits = [
            targets[position] - len(assignments[position]) for position in range(3)
        ]
        destination = max(
            eligible_partitions,
            key=lambda position: (
                deficits[position],
                normalized_fractions[position],
                -position,
            ),
        )
        assignments[destination].extend(indices)

    return MolecularSplit(
        train=tuple(sorted(assignments[0])),
        validation=tuple(sorted(assignments[1])),
        test=tuple(sorted(assignments[2])),
    )
