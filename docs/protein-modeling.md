# Protein-aware modeling baseline

## Scope

This module is a transparent reference baseline for continuous
protein-ligand prediction. It is **not a pretrained protein model**. It uses no
learned sequence embeddings, molecular graph network, structure prediction, or
external training corpus.

The baseline exists to establish a reproducible lower-complexity comparison
before introducing heavier models. Results are valid only for the records
provided to a run; the package ships no benchmark scores and makes no external
performance claims.

## Input records

`ProteinLigandRecord` requires:

- unique record, protein, and ligand identifiers;
- a non-empty amino-acid sequence;
- a protein-family identifier;
- a ligand representation such as a canonical SMILES string;
- a ligand group identifier, such as a precomputed Bemis-Murcko scaffold or
  chemistry-cluster ID;
- a finite continuous target, its name, and optionally its unit and source.

The module validates data but deliberately does not derive scaffold IDs. A
chemistry-aware upstream process should compute those IDs consistently.
Ambiguous amino-acid symbols are accepted and measured as an ambiguous-residue
fraction; other sequence characters are rejected.

## Leakage-resistant splitting

The splitter builds connected components across protein families and ligand
groups. If two records share either identifier, directly or through a chain of
other records, they remain in the same partition. This guarantees that neither
a protein family nor a ligand group crosses train, validation, and test.

Components are ordered using SHA-256 over record IDs and a configured seed, so
the result is deterministic and independent of Python's randomized `hash()`.
Requested fractions are approximate because a connected component cannot be
split safely. The splitter fails if there are too few independent components
to populate all requested partitions.

## Features and model

Protein features contain:

- frequencies for the 20 standard amino acids;
- log sequence length;
- ambiguous-residue fraction.

Ligand features are signed, hashed character n-gram counts from the supplied
ligand string, normalized to unit L2 norm. Hash collisions are expected, and
the representation does not encode molecular topology as faithfully as
chemistry-specific graph features.

`fit_ridge` standardizes each feature using training-set statistics and fits
ridge regression with NumPy. The intercept is not regularized. Constant
features receive a scale of one. This implementation is appropriate as a
baseline, not as a substitute for uncertainty estimation, calibrated
prospective validation, or a pretrained sequence/structure model.

For an explicit pretrained comparison, `protein_embedding_matrix` aligns
externally generated vectors by protein ID and
`ProteinEmbeddingProvenance` records the model revision, layer, and pooling.
`append_embeddings` combines them with the transparent baseline features. These
utilities deliberately do not download a model, hide missing proteins, or claim
that an embedding experiment has been run.

## Metrics and artifacts

Runs report count, mean absolute error, root mean squared error, and R-squared
for each populated partition. R-squared is serialized as `null` when it is
undefined for a single observation or a constant target.

The JSON result contains:

- fitted ridge parameters and feature names;
- actual metrics calculated from the supplied records;
- partition record IDs;
- a model card with intended use and limitations;
- UTC creation time, runtime versions, configuration, record count, and a
  SHA-256 fingerprint of canonicalized input records.

No external or fabricated results are inserted into the artifact.

## Minimal use

```python
from pharmascope.protein import ProteinLigandRecord, fit_baseline

records = [
    ProteinLigandRecord(
        record_id="measurement-1",
        protein_id="P12345",
        protein_sequence="MKTAYIAKQRQISFVKSHFSRQ",
        protein_family="example-family",
        ligand_id="compound-1",
        ligand_representation="CCO",
        ligand_group="scaffold-1",
        target=6.4,
        target_name="pActivity",
        target_unit="log10 molar",
        source="local assay table",
    ),
    # Add enough independent family/group components for requested holdouts.
]

run = fit_baseline(records, seed=42)
run.result.save("protein-baseline-result.json")
predictions = run.model.predict(new_feature_matrix)
```

Use `featurize_records` with the same `FeatureConfig` to construct
`new_feature_matrix`. A production inference path should also check that target
definitions, sequence conventions, and ligand canonicalization match training.
