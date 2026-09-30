"""Tests for the transparent protein-ligand modeling baseline."""

import json

import numpy as np
import pytest

from pharmascope.protein import (
    FeatureConfig,
    ModelingResult,
    ProteinEmbeddingProvenance,
    ProteinLigandRecord,
    append_embeddings,
    assert_group_isolation,
    deterministic_group_split,
    feature_names,
    featurize_records,
    fit_baseline,
    fit_ridge,
    protein_embedding_matrix,
    regression_metrics,
)


def make_record(
    index: int,
    *,
    family: str | None = None,
    ligand_group: str | None = None,
) -> ProteinLigandRecord:
    return ProteinLigandRecord(
        record_id=f"record-{index}",
        protein_id=f"protein-{index}",
        protein_sequence="ACDEFGHIKLMNPQRSTVWY",
        protein_family=family or f"family-{index}",
        ligand_id=f"ligand-{index}",
        ligand_representation=f"CCN{index}",
        ligand_group=ligand_group or f"scaffold-{index}",
        target=float(index),
        target_name="pActivity",
        target_unit="log10 molar",
        source="synthetic unit-test fixture",
    )


def test_record_normalizes_sequence_and_validates_values():
    record = ProteinLigandRecord(
        record_id="r1",
        protein_id="p1",
        protein_sequence="acde\nX",
        protein_family="kinase",
        ligand_id="l1",
        ligand_representation="CCO",
        ligand_group="scaffold-1",
        target=7,
    )
    assert record.protein_sequence == "ACDEX"
    assert record.target == 7.0

    with pytest.raises(ValueError, match="unsupported residues"):
        make_record(1).__class__(
            **{
                **make_record(1).to_dict(),
                "record_id": "bad",
                "protein_sequence": "ACD*",
            }
        )
    with pytest.raises(ValueError, match="finite"):
        ProteinLigandRecord(
            **{**make_record(2).to_dict(), "record_id": "nan", "target": np.nan}
        )


def test_group_split_is_deterministic_and_prevents_both_leakage_types():
    records = [
        make_record(0, family="family-a", ligand_group="group-a"),
        make_record(1, family="family-a", ligand_group="group-b"),
        # This links group-b to family-b, so all three records must stay together.
        make_record(2, family="family-b", ligand_group="group-b"),
        make_record(3),
        make_record(4),
        make_record(5),
    ]
    first = deterministic_group_split(
        records, validation_fraction=0.2, test_fraction=0.2, seed=17
    )
    second = deterministic_group_split(
        records, validation_fraction=0.2, test_fraction=0.2, seed=17
    )
    assert first == second
    assert_group_isolation(records, first)

    owners = {}
    for partition, indices in first.as_dict().items():
        for index in indices:
            owners[index] = partition
    assert owners[0] == owners[1] == owners[2]


def test_split_rejects_too_few_independent_components():
    records = [
        make_record(0, family="same", ligand_group="same"),
        make_record(1, family="same", ligand_group="same"),
    ]
    with pytest.raises(ValueError, match="not enough independent"):
        deterministic_group_split(
            records, validation_fraction=0.2, test_fraction=0.2
        )


def test_features_are_deterministic_and_have_documented_width():
    records = [make_record(0), make_record(1)]
    config = FeatureConfig(ligand_hash_size=16, ligand_ngram_min=2, ligand_ngram_max=3)
    first = featurize_records(records, config)
    second = featurize_records(records, config)

    assert first.shape == (2, 20 + 2 + 16)
    np.testing.assert_array_equal(first, second)
    assert len(feature_names(config)) == first.shape[1]
    assert np.isclose(first[0, :20].sum(), 1.0)


def test_ridge_fits_and_serialized_model_predicts():
    features = np.arange(12, dtype=float).reshape(6, 2)
    targets = 2.0 * features[:, 0] - features[:, 1] + 3.0
    model = fit_ridge(features, targets, alpha=0.0)

    np.testing.assert_allclose(model.predict(features), targets, atol=1e-10)
    restored = model.from_dict(model.to_dict())
    np.testing.assert_allclose(restored.predict(features), model.predict(features))


def test_regression_metrics_and_undefined_r_squared():
    metrics = regression_metrics([1.0, 2.0, 3.0], [1.0, 2.0, 4.0])
    assert metrics.count == 3
    assert metrics.mean_absolute_error == pytest.approx(1 / 3)
    assert metrics.root_mean_squared_error == pytest.approx(np.sqrt(1 / 3))
    assert metrics.r_squared == pytest.approx(0.5)

    assert regression_metrics([2.0], [2.0]).r_squared is None
    assert regression_metrics([2.0, 2.0], [2.0, 2.0]).r_squared is None


def test_end_to_end_result_is_honest_and_json_round_trips(tmp_path):
    records = [make_record(index) for index in range(8)]
    run = fit_baseline(
        records,
        feature_config=FeatureConfig(ligand_hash_size=8),
        validation_fraction=0.25,
        test_fraction=0.25,
        seed=9,
    )

    assert "not a pretrained protein model" in run.result.model_card.summary
    assert run.result.provenance.record_count == len(records)
    assert set(run.result.metrics) == {"train", "validation", "test"}
    assert len(run.result.provenance.dataset_sha256) == 64

    path = tmp_path / "result.json"
    run.result.save(path)
    raw = json.loads(path.read_text())
    assert raw["artifact_version"] == 1
    assert ModelingResult.load(path) == run.result


def test_pretrained_protein_embeddings_are_aligned_and_versioned():
    records = [make_record(0), make_record(1)]
    provenance = ProteinEmbeddingProvenance(
        model_name="example-protein-encoder",
        model_revision="immutable-revision",
        layer="final",
        pooling="mean",
    )
    embeddings = protein_embedding_matrix(
        records,
        {
            "protein-0": [1.0, 2.0],
            "protein-1": [3.0, 4.0],
        },
    )
    combined = append_embeddings(np.ones((2, 3)), embeddings)

    assert provenance.layer == "final"
    assert combined.shape == (2, 5)
    with pytest.raises(ValueError, match="protein-1"):
        protein_embedding_matrix(records, {"protein-0": [1.0, 2.0]})
