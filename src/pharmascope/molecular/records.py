"""Validated records for binary molecular safety endpoints."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class SmilesRecord:
    """One compound observation for one binary safety endpoint.

    This schema validates the record shape, not the chemical validity of the
    SMILES string. Chemical parsing requires a toolkit such as RDKit.
    """

    compound_id: str
    smiles: str
    endpoint: str
    label: int
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("compound_id", "smiles", "endpoint"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if any(character.isspace() for character in self.smiles):
            raise ValueError("smiles must not contain whitespace")
        if isinstance(self.label, bool) or self.label not in (0, 1):
            raise ValueError("label must be the integer 0 or 1")
        if not isinstance(self.metadata, Mapping):
            raise ValueError("metadata must be a mapping")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        return {
            "compound_id": self.compound_id,
            "smiles": self.smiles,
            "endpoint": self.endpoint,
            "label": self.label,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SmilesRecord":
        """Construct a record while rejecting missing required fields."""

        required = ("compound_id", "smiles", "endpoint", "label")
        missing = [name for name in required if name not in value]
        if missing:
            raise ValueError(f"missing required fields: {', '.join(missing)}")
        return cls(
            compound_id=value["compound_id"],
            smiles=value["smiles"],
            endpoint=value["endpoint"],
            label=value["label"],
            metadata=value.get("metadata", {}),
        )
