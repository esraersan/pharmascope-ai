"""Dependency-light molecular safety modeling utilities.

The split and fingerprint implementations in this package operate on SMILES
text. They do not infer molecular graphs and must not be described as
chemistry-aware fingerprints or Bemis-Murcko scaffold splitting.
"""

from .artifacts import ExperimentConfig, ExperimentResult, generate_model_card
from .baseline import FingerprintLogisticRegression
from .domain import ApplicabilityAssessment, assess_applicability, error_analysis
from .embeddings import EmbeddingProvenance, embedding_matrix
from .fingerprints import hashed_token_fingerprint, tanimoto_similarity
from .metrics import BinaryMetrics, binary_metrics, calibration_curve, roc_auc
from .records import SmilesRecord
from .split import MolecularSplit, deterministic_token_framework_split

__all__ = [
    "ApplicabilityAssessment",
    "BinaryMetrics",
    "ExperimentConfig",
    "ExperimentResult",
    "EmbeddingProvenance",
    "FingerprintLogisticRegression",
    "MolecularSplit",
    "SmilesRecord",
    "assess_applicability",
    "binary_metrics",
    "calibration_curve",
    "deterministic_token_framework_split",
    "error_analysis",
    "embedding_matrix",
    "generate_model_card",
    "hashed_token_fingerprint",
    "roc_auc",
    "tanimoto_similarity",
]
