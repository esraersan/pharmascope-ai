"""Provenance, model cards, and JSON serialization for baseline results."""

from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from .schema import ProteinLigandRecord

BASELINE_STATEMENT = (
    "This is a simple ridge-regression baseline using protein sequence "
    "composition and hashed ligand-string features. It is not a pretrained "
    "protein model and does not learn structural or evolutionary representations."
)


@dataclass(frozen=True)
class Provenance:
    created_at_utc: str
    dataset_sha256: str
    record_count: int
    python_version: str
    numpy_version: str
    feature_config: Mapping[str, Any]
    split_config: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ModelCard:
    name: str
    summary: str
    intended_use: str
    limitations: tuple[str, ...]
    target_name: str
    target_unit: str

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["limitations"] = list(self.limitations)
        return result


@dataclass(frozen=True)
class ModelingResult:
    """Fully serializable fitted baseline and its measured split metrics."""

    model: Mapping[str, Any]
    model_card: ModelCard
    provenance: Provenance
    split_record_ids: Mapping[str, Sequence[str]]
    metrics: Mapping[str, Mapping[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_version": 1,
            "model": dict(self.model),
            "model_card": self.model_card.to_dict(),
            "provenance": self.provenance.to_dict(),
            "split_record_ids": {
                name: list(record_ids)
                for name, record_ids in self.split_record_ids.items()
            },
            "metrics": {
                name: dict(values) for name, values in self.metrics.items()
            },
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(
            self.to_dict(),
            indent=indent,
            sort_keys=True,
            allow_nan=False,
        )

    def save(self, path: str | Path) -> None:
        Path(path).write_text(self.to_json() + "\n", encoding="utf-8")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ModelingResult:
        if value.get("artifact_version") != 1:
            raise ValueError("unsupported artifact_version")
        card_value = dict(value["model_card"])
        card_value["limitations"] = tuple(card_value["limitations"])
        provenance_value = dict(value["provenance"])
        return cls(
            model=dict(value["model"]),
            model_card=ModelCard(**card_value),
            provenance=Provenance(**provenance_value),
            split_record_ids={
                name: tuple(record_ids)
                for name, record_ids in value["split_record_ids"].items()
            },
            metrics={
                name: dict(metrics) for name, metrics in value["metrics"].items()
            },
        )

    @classmethod
    def from_json(cls, text: str) -> ModelingResult:
        return cls.from_dict(json.loads(text))

    @classmethod
    def load(cls, path: str | Path) -> ModelingResult:
        return cls.from_json(Path(path).read_text(encoding="utf-8"))


def dataset_fingerprint(records: Sequence[ProteinLigandRecord]) -> str:
    """Hash canonical records so an artifact can identify its exact input."""

    encoded = "\n".join(
        json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"))
        for record in sorted(records, key=lambda item: item.record_id)
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def create_provenance(
    records: Sequence[ProteinLigandRecord],
    *,
    feature_config: Mapping[str, Any],
    split_config: Mapping[str, Any],
) -> Provenance:
    return Provenance(
        created_at_utc=datetime.now(timezone.utc).isoformat(),
        dataset_sha256=dataset_fingerprint(records),
        record_count=len(records),
        python_version=platform.python_version(),
        numpy_version=np.__version__,
        feature_config=dict(feature_config),
        split_config=dict(split_config),
    )
