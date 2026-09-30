"""End-to-end orchestration for the transparent protein-ligand baseline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from .artifacts import (
    BASELINE_STATEMENT,
    ModelCard,
    ModelingResult,
    create_provenance,
)
from .features import FeatureConfig, feature_names, featurize_records
from .metrics import regression_metrics
from .model import RidgeRegressor, fit_ridge
from .schema import ProteinLigandRecord
from .splits import assert_group_isolation, deterministic_group_split


@dataclass(frozen=True)
class BaselineRun:
    model: RidgeRegressor
    result: ModelingResult


def fit_baseline(
    records: Sequence[ProteinLigandRecord],
    *,
    feature_config: FeatureConfig | None = None,
    alpha: float = 1.0,
    validation_fraction: float = 0.1,
    test_fraction: float = 0.2,
    seed: int = 0,
) -> BaselineRun:
    """Split, featurize, fit, evaluate, and package the baseline.

    Metrics describe only the supplied records. This function does not claim
    external validation or pretrained-model performance.
    """

    if not records:
        raise ValueError("records must not be empty")
    target_names = {record.target_name for record in records}
    target_units = {record.target_unit for record in records}
    if len(target_names) != 1 or len(target_units) != 1:
        raise ValueError("all records must use the same target_name and target_unit")

    config = feature_config or FeatureConfig()
    split = deterministic_group_split(
        records,
        validation_fraction=validation_fraction,
        test_fraction=test_fraction,
        seed=seed,
    )
    assert_group_isolation(records, split)

    features = featurize_records(records, config)
    targets = np.asarray([record.target for record in records], dtype=float)
    model = fit_ridge(
        features[list(split.train)],
        targets[list(split.train)],
        alpha=alpha,
    )

    partitions = {
        "train": split.train,
        "validation": split.validation,
        "test": split.test,
    }
    measured_metrics = {}
    split_record_ids = {}
    for name, indices in partitions.items():
        split_record_ids[name] = tuple(records[index].record_id for index in indices)
        if indices:
            predicted = model.predict(features[list(indices)])
            measured_metrics[name] = regression_metrics(
                targets[list(indices)], predicted
            ).to_dict()

    split_config = {
        "method": "connected_protein_family_and_ligand_group_holdout",
        "validation_fraction": validation_fraction,
        "test_fraction": test_fraction,
        "seed": seed,
    }
    serialized_model = model.to_dict()
    serialized_model["feature_names"] = list(feature_names(config))
    result = ModelingResult(
        model=serialized_model,
        model_card=ModelCard(
            name="Protein-ligand composition/hash ridge baseline",
            summary=BASELINE_STATEMENT,
            intended_use=(
                "A reproducible reference point for continuous protein-ligand "
                "prediction experiments on user-supplied measurements."
            ),
            limitations=(
                "Sequence composition discards residue order and protein structure.",
                "Hashed ligand strings can collide and are not molecular graphs.",
                "Performance may not transfer beyond the supplied grouped dataset.",
                "Holdout proportions are approximate when connected groups are large.",
            ),
            target_name=next(iter(target_names)),
            target_unit=next(iter(target_units)),
        ),
        provenance=create_provenance(
            records,
            feature_config=config.to_dict(),
            split_config=split_config,
        ),
        split_record_ids=split_record_ids,
        metrics=measured_metrics,
    )
    return BaselineRun(model=model, result=result)
