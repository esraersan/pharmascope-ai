"""Dependency-light protein-ligand modeling baseline.

This package is not a pretrained protein model. It provides transparent
composition/hash features and NumPy ridge regression as an auditable baseline.
"""

from .artifacts import (
    BASELINE_STATEMENT,
    ModelCard,
    ModelingResult,
    Provenance,
    create_provenance,
    dataset_fingerprint,
)
from .embeddings import (
    ProteinEmbeddingProvenance,
    append_embeddings,
    protein_embedding_matrix,
)
from .features import FeatureConfig, feature_names, featurize_records
from .metrics import RegressionMetrics, regression_metrics
from .model import RidgeRegressor, fit_ridge
from .pipeline import BaselineRun, fit_baseline
from .schema import ProteinLigandRecord
from .splits import SplitIndices, assert_group_isolation, deterministic_group_split

__all__ = [
    "BASELINE_STATEMENT",
    "BaselineRun",
    "FeatureConfig",
    "ModelCard",
    "ModelingResult",
    "ProteinLigandRecord",
    "ProteinEmbeddingProvenance",
    "Provenance",
    "RegressionMetrics",
    "RidgeRegressor",
    "SplitIndices",
    "assert_group_isolation",
    "append_embeddings",
    "create_provenance",
    "dataset_fingerprint",
    "deterministic_group_split",
    "feature_names",
    "featurize_records",
    "fit_baseline",
    "fit_ridge",
    "protein_embedding_matrix",
    "regression_metrics",
]
