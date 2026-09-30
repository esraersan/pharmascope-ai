"""Experiment configuration, result, and model-card artifacts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    """Serializable inputs for one molecular endpoint experiment."""

    endpoint: str
    dataset_name: str
    dataset_source: str
    seed: int = 0
    split_fractions: tuple[float, float, float] = (0.8, 0.1, 0.1)
    fingerprint_bits: int = 2048
    fingerprint_ngram_range: tuple[int, int] = (1, 3)
    model_parameters: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("endpoint", "dataset_name", "dataset_source"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if (
            len(self.split_fractions) != 3
            or any(value < 0 for value in self.split_fractions)
            or sum(self.split_fractions) <= 0
        ):
            raise ValueError("split_fractions must contain three valid values")
        if self.fingerprint_bits <= 0:
            raise ValueError("fingerprint_bits must be positive")
        low, high = self.fingerprint_ngram_range
        if low <= 0 or high < low:
            raise ValueError("fingerprint_ngram_range is invalid")

    @property
    def experiment_id(self) -> str:
        """Return a stable identifier derived from the complete configuration."""

        encoded = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["split_fractions"] = list(self.split_fractions)
        value["fingerprint_ngram_range"] = list(self.fingerprint_ngram_range)
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ExperimentConfig":
        return cls(
            endpoint=value["endpoint"],
            dataset_name=value["dataset_name"],
            dataset_source=value["dataset_source"],
            seed=value.get("seed", 0),
            split_fractions=tuple(value.get("split_fractions", (0.8, 0.1, 0.1))),
            fingerprint_bits=value.get("fingerprint_bits", 2048),
            fingerprint_ngram_range=tuple(
                value.get("fingerprint_ngram_range", (1, 3))
            ),
            model_parameters=value.get("model_parameters", {}),
        )


@dataclass(frozen=True, slots=True)
class ExperimentResult:
    """Observed outputs from a run; callers must supply all measured values."""

    experiment_id: str
    split_method: str
    split_counts: Mapping[str, int]
    metrics: Mapping[str, Mapping[str, float]]
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.experiment_id or not self.split_method:
            raise ValueError("experiment_id and split_method are required")
        if any(count < 0 for count in self.split_counts.values()):
            raise ValueError("split counts must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "split_method": self.split_method,
            "split_counts": dict(self.split_counts),
            "metrics": {
                partition: dict(values)
                for partition, values in self.metrics.items()
            },
            "notes": list(self.notes),
        }


def write_json_artifact(
    artifact: ExperimentConfig | ExperimentResult, destination: str | Path
) -> None:
    """Write an artifact as stable, human-readable JSON."""

    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(artifact.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def generate_model_card(
    config: ExperimentConfig,
    result: ExperimentResult | None = None,
    *,
    intended_use: str,
    limitations: tuple[str, ...] = (),
) -> str:
    """Generate Markdown without inventing missing performance values."""

    if result is not None and result.experiment_id != config.experiment_id:
        raise ValueError("result experiment_id does not match the configuration")
    measured_results = (
        "_No experiment results were supplied._"
        if result is None
        else "```json\n"
        + json.dumps(result.to_dict(), indent=2, sort_keys=True)
        + "\n```"
    )
    limitation_lines = [
        "- Features are hashes of lexical SMILES token n-grams, not molecular "
        "graph fingerprints.",
        "- The grouped split is not a Bemis-Murcko scaffold split and may place "
        "equivalent non-canonical SMILES in different partitions.",
        "- Applicability scores measure similarity in this lexical feature "
        "space; they are not proof of chemical or clinical applicability.",
        "- Predictions are research outputs and must not guide patient care.",
        *[f"- {item}" for item in limitations],
    ]
    return "\n".join(
        [
            f"# Model card: {config.endpoint}",
            "",
            "## Intended use",
            intended_use.strip(),
            "",
            "## Data provenance",
            f"- Dataset: {config.dataset_name}",
            f"- Source: {config.dataset_source}",
            "- No claim is made here that the dataset was downloaded or run.",
            "",
            "## Configuration",
            "```json",
            json.dumps(config.to_dict(), indent=2, sort_keys=True),
            "```",
            "",
            "## Measured results",
            measured_results,
            "",
            "## Limitations",
            *limitation_lines,
            "",
        ]
    )
