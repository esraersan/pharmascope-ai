# Molecular safety modeling

This package provides a small, reproducible baseline for binary safety
endpoints represented by SMILES strings. It is designed to run with the
project's existing Python and NumPy dependencies.

## Scientific scope

The implementation is deliberately lexical. It tokenizes SMILES text and does
not parse molecular graphs, perceive aromaticity, standardize structures, or
canonicalize tautomers and salts.

- `token_framework_key` produces a **SMILES token/framework key**. It is not a
  Bemis-Murcko scaffold.
- `hashed_token_fingerprint` hashes token n-grams. It is not an ECFP/Morgan or
  other chemistry-aware fingerprint.
- Tanimoto applicability scores are similarities in that lexical fingerprint
  space, not evidence that a prediction is chemically or clinically valid.

Equivalent compounds encoded with different valid SMILES can receive different
keys and fingerprints. Production chemistry work should add explicit
standardization and a validated toolkit such as RDKit, then name and version
that process.

## Workflow

1. Validate each observation as a `SmilesRecord`. Validation checks data shape,
   not chemical validity.
2. Call `deterministic_token_framework_split`. Records sharing an exact lexical
   framework key stay together. The greedy assignment approximates requested
   sizes but can produce empty or imbalanced partitions when groups are large.
3. Build features with `fingerprint_matrix`.
4. Fit `FingerprintLogisticRegression` as a transparent baseline. Fit only on
   training data; select any threshold or hyperparameters using validation data.
5. Report untouched test-set ROC-AUC, Brier score, calibration bins, and
   expected calibration error. ROC-AUC is undefined when a partition contains
   one class, and the metric helper raises an error rather than inventing a
   value.
6. Use nearest-training similarity and ranked error cases to inspect failures,
   including out-of-domain errors.
7. Save the exact `ExperimentConfig`, observed `ExperimentResult`, and generated
   model card.

`embedding_matrix` provides a strict adapter for comparing the lexical baseline
with externally generated pretrained molecular embeddings. It aligns vectors by
compound ID, rejects missing or non-finite vectors, and pairs with an
`EmbeddingProvenance` record containing the model name, immutable revision, and
pooling strategy. The adapter does not download a model or imply that an
embedding experiment has been run.

## Evidence and leakage controls

- Deduplicate or reconcile conflicting labels before splitting.
- Keep repeated measurements, salts, stereoisomers, and close analogues grouped
  using chemistry-aware identifiers when available. The lexical grouping alone
  cannot guarantee this.
- Record endpoint definition, assay protocol, units, censoring, label rules,
  species, and provenance. A binary label without this context is not portable.
- Fit preprocessing on training data only.
- Preserve dataset version or checksum and code revision outside the result
  artifact.
- Report class counts for every partition and uncertainty intervals where
  sample size permits.
- Do not select a model on the test set or interpret a random record split as
  prospective chemical-generalization evidence.

## Interpretation

ROC-AUC measures ranking, not calibration or clinical utility. Brier score
combines calibration and discrimination and depends on prevalence. Calibration
bins are descriptive and unstable with small counts. Applicability thresholds
must be chosen on validation evidence for the endpoint; the library default is
only an operational starting point.

No external dataset or experiment result is bundled or claimed. The example
configuration is a template and uses an explicit placeholder source.
