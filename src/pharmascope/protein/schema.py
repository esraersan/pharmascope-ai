"""Validated, dependency-light schemas for protein-ligand regression records."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

_ALLOWED_RESIDUES = frozenset("ACDEFGHIKLMNPQRSTVWYBXZJUO")


def _required_text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _json_metadata(value: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(value)
    try:
        json.dumps(result, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("metadata must contain only finite JSON values") from exc
    return result


@dataclass(frozen=True)
class ProteinLigandRecord:
    """One measured protein-ligand pair and its grouping identifiers.

    ``protein_family`` and ``ligand_group`` are required because they are the
    units held out by the leakage-resistant splitter. ``ligand_group`` may be a
    molecular scaffold ID, a cluster ID, or another precomputed grouping ID;
    this package intentionally does not infer chemistry from a ligand string.
    """

    record_id: str
    protein_id: str
    protein_sequence: str
    protein_family: str
    ligand_id: str
    ligand_representation: str
    ligand_group: str
    target: float
    target_name: str = "activity"
    target_unit: str = ""
    source: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "record_id",
            "protein_id",
            "protein_family",
            "ligand_id",
            "ligand_representation",
            "ligand_group",
            "target_name",
        ):
            object.__setattr__(self, name, _required_text(getattr(self, name), name))

        sequence = "".join(self.protein_sequence.split()).upper()
        if not sequence:
            raise ValueError("protein_sequence must be non-empty")
        invalid = sorted(set(sequence) - _ALLOWED_RESIDUES)
        if invalid:
            raise ValueError(
                "protein_sequence contains unsupported residues: "
                + ", ".join(invalid)
            )
        object.__setattr__(self, "protein_sequence", sequence)

        try:
            target = float(self.target)
        except (TypeError, ValueError) as exc:
            raise ValueError("target must be a finite number") from exc
        if not math.isfinite(target):
            raise ValueError("target must be a finite number")
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "target_unit", self.target_unit.strip())
        object.__setattr__(self, "source", self.source.strip())
        object.__setattr__(self, "metadata", _json_metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ProteinLigandRecord:
        """Validate and construct a record from a mapping."""

        return cls(**dict(value))
