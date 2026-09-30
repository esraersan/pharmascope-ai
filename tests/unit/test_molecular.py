"""Unit tests for dependency-light molecular safety utilities."""

import json

import numpy as np
import pytest

from pharmascope.molecular.artifacts import (
    ExperimentConfig,
    ExperimentResult,
    generate_model_card,
    write_json_artifact,
)
from pharmascope.molecular.baseline import FingerprintLogisticRegression
from pharmascope.molecular.domain import assess_applicability, error_analysis
from pharmascope.molecular.embeddings import EmbeddingProvenance, embedding_matrix
from pharmascope.molecular.fingerprints import (
    fingerprint_matrix,
    hashed_token_fingerprint,
    tanimoto_similarity,
    tokenize_smiles,
)
from pharmascope.molecular.metrics import (
    binary_metrics,
    brier_score,
    calibration_curve,
    roc_auc,
)
from pharmascope.molecular.records import SmilesRecord
from pharmascope.molecular.split import (
    deterministic_token_framework_split,
    token_framework_key,
)


def _record(index: int, smiles: str, label: int) -> SmilesRecord:
    return SmilesRecord(
        compound_id=f"compound-{index}",
        smiles=smiles,
        endpoint="example-toxicity",
        label=label,
    )


def test_smiles_record_round_trip_and_validation():
    record = _record(1, "CC(=O)O", 1)
    assert SmilesRecord.from_dict(record.to_dict()) == record

    with pytest.raises(ValueError, match="integer 0 or 1"):
        _record(2, "CCO", 2)
    with pytest.raises(ValueError, match="whitespace"):
        _record(3, "CC O", 0)


def test_token_fingerprint_is_deterministic_and_binary():
    assert tokenize_smiles("ClC=C([C@H](O)Br)C") == (
        "Cl",
        "C",
        "=",
        "C",
        "(",
        "[C@H]",
        "(",
        "O",
        ")",
        "Br",
        ")",
        "C",
    )
    first = hashed_token_fingerprint("CC(=O)O", n_bits=128)
    second = hashed_token_fingerprint("CC(=O)O", n_bits=128)
    assert np.array_equal(first, second)
    assert first.dtype == np.uint8
    assert set(np.unique(first)).issubset({0, 1})


def test_fingerprint_matrix_and_tanimoto():
    matrix = fingerprint_matrix(["CCO", "CCO", "N#N"], n_bits=256)
    assert matrix.shape == (3, 256)
    assert tanimoto_similarity(matrix[0], matrix[1]) == 1.0
    assert 0.0 <= tanimoto_similarity(matrix[0], matrix[2]) < 1.0
    assert tanimoto_similarity(
        matrix[0].astype(float), matrix[1].astype(float)
    ) == pytest.approx(1.0)


def test_token_framework_split_is_deterministic_and_grouped():
    records = [
        _record(0, "CCO", 0),
        _record(1, "CCO", 1),
        _record(2, "CCN", 0),
        _record(3, "N#N", 1),
        _record(4, "c1ccccc1", 0),
        _record(5, "C1CCCCC1", 1),
    ]
    first = deterministic_token_framework_split(
        records, fractions=(0.5, 0.25, 0.25), seed=17
    )
    second = deterministic_token_framework_split(
        records, fractions=(0.5, 0.25, 0.25), seed=17
    )
    assert first == second
    assert sorted(first.train + first.validation + first.test) == list(
        range(len(records))
    )
    partitions = (first.train, first.validation, first.test)
    for framework in {token_framework_key(record.smiles) for record in records}:
        containing_partitions = sum(
            any(
                token_framework_key(records[index].smiles) == framework
                for index in part
            )
            for part in partitions
        )
        assert containing_partitions == 1
    assert first.method == "lexical_smiles_token_framework"

    train_only = deterministic_token_framework_split(
        records, fractions=(1.0, 0.0, 0.0), seed=17
    )
    assert train_only.train == tuple(range(len(records)))
    assert train_only.validation == ()
    assert train_only.test == ()


def test_binary_metrics_known_values_and_ties():
    labels = [0, 0, 1, 1]
    probabilities = [0.1, 0.4, 0.35, 0.8]
    assert roc_auc(labels, probabilities) == pytest.approx(0.75)
    assert brier_score(labels, probabilities) == pytest.approx(0.158125)

    tied_auc = roc_auc([0, 1], [0.5, 0.5])
    assert tied_auc == pytest.approx(0.5)
    result = binary_metrics(labels, probabilities, n_bins=2)
    assert result.roc_auc == pytest.approx(0.75)
    assert 0 <= result.expected_calibration_error <= 1
    assert sum(item.count for item in result.calibration) == 4


def test_metrics_reject_undefined_auc_and_bad_probabilities():
    with pytest.raises(ValueError, match="both positive and negative"):
        roc_auc([1, 1], [0.2, 0.8])
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        calibration_curve([0, 1], [-0.1, 0.5])


def test_logistic_baseline_learns_separable_data():
    features = np.array(
        [[0, 0], [0, 1], [1, 0], [1, 1]], dtype=np.uint8
    )
    labels = np.array([0, 0, 1, 1])
    model = FingerprintLogisticRegression(
        learning_rate=0.5, max_iter=1000, l2=0.0
    ).fit(features, labels)
    probabilities = model.predict_proba(features)
    assert np.all(probabilities[:2] < 0.5)
    assert np.all(probabilities[2:] > 0.5)
    assert model.n_iter_ > 0


def test_applicability_and_error_analysis():
    training = fingerprint_matrix(["CCO", "N#N"], n_bits=128)
    queries = fingerprint_matrix(["CCO", "CCCC"], n_bits=128)
    assessment = assess_applicability(
        training, queries, similarity_threshold=0.8
    )
    assert assessment.nearest_similarity[0] == 1.0
    assert assessment.nearest_training_index[0] == 0
    assert assessment.in_domain.tolist() == [True, False]

    records = [_record(0, "CCO", 0), _record(1, "N#N", 1)]
    analysis = error_analysis(
        records,
        [0.9, 0.2],
        nearest_similarities=[0.4, 0.8],
    )
    assert analysis.false_positive == 1
    assert analysis.false_negative == 1
    assert analysis.cases[0].compound_id == "compound-0"
    assert analysis.cases[0].nearest_similarity == pytest.approx(0.4)


def test_experiment_artifacts_and_model_card(tmp_path):
    config = ExperimentConfig(
        endpoint="example-toxicity",
        dataset_name="unit-test-fixture",
        dataset_source="in-memory synthetic fixture",
        model_parameters={"learning_rate": 0.1},
    )
    assert config.experiment_id == config.experiment_id

    result = ExperimentResult(
        experiment_id=config.experiment_id,
        split_method="lexical_smiles_token_framework",
        split_counts={"train": 4, "validation": 2, "test": 2},
        metrics={"test": {"roc_auc": 0.75, "brier_score": 0.2}},
        notes=("Synthetic unit-test values only.",),
    )
    destination = tmp_path / "result.json"
    write_json_artifact(result, destination)
    assert json.loads(destination.read_text())["experiment_id"] == config.experiment_id

    empty_card = generate_model_card(
        config, intended_use="Test the artifact generator."
    )
    assert "No experiment results were supplied" in empty_card
    assert "not a Bemis-Murcko scaffold split" in empty_card

    measured_card = generate_model_card(
        config,
        result,
        intended_use="Test the artifact generator.",
        limitations=("Fixture is not scientific evidence.",),
    )
    assert '"roc_auc": 0.75' in measured_card
    assert "Fixture is not scientific evidence." in measured_card


def test_pretrained_embedding_alignment_requires_provenance_and_full_coverage():
    records = [_record(0, "CCO", 0), _record(1, "N#N", 1)]
    provenance = EmbeddingProvenance(
        model_name="example-encoder",
        model_revision="immutable-revision",
        pooling="mean",
    )
    matrix = embedding_matrix(
        records,
        {
            "compound-0": [1.0, 2.0],
            "compound-1": [3.0, 4.0],
        },
    )

    assert provenance.model_revision == "immutable-revision"
    assert matrix.shape == (2, 2)
    with pytest.raises(ValueError, match="compound-1"):
        embedding_matrix(records, {"compound-0": [1.0, 2.0]})
