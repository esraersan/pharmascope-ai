# Changelog

## Unreleased

### Scientific validity

- Replaced query-history-dependent safety counts with complete, immutable,
  checksummed FAERS snapshots.
- Preserved suspect, concomitant, and interacting drug roles.
- Added follow-up-version replacement and report-level deduplication.
- Added sourced historical benchmark definitions, comparator cases, temporal
  cutoffs, uncertainty, an IC-like comparator, and generated result metadata.

### Research modules

- Added a molecular-safety baseline with deterministic group-aware splitting,
  lexical fingerprints, logistic regression, calibration, applicability-domain
  analysis, model cards, and pretrained-embedding integration.
- Added a protein–ligand baseline with family/scaffold isolation,
  sequence-composition and ligand features, ridge regression, model cards, and
  pretrained protein-embedding integration.
- Added deterministic life-science agent tasks and graders for answers,
  numeric tolerance, sets, citations, tools, and appropriate refusal.

### Engineering

- Added database bootstrap and migration SQL, CLI commands, a locked `uv`
  environment, integration/API tests, CI linting and coverage, containerized
  dashboard configuration, data/model documentation, and an MIT license.
- Reworked the dashboard around complete reference populations and optional
  temporal benchmark artifacts.
- Removed claims of implemented RAG, LangGraph orchestration, semantic PubMed
  search, and completed real-data benchmarks.
