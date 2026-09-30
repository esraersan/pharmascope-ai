# pharmascope-ai

A reproducible research codebase for pharmacovigilance, molecular-safety
baselines, protein–ligand generalization, and verifiable life-science model
evaluations.

[![CI](https://github.com/esraersan/pharmascope-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/esraersan/pharmascope-ai/actions)
![Python](https://img.shields.io/badge/python-3.12-blue)

## What is implemented

- checksummed, immutable FAERS snapshot imports with follow-up-version handling;
- suspect/concomitant drug-role preservation and report-level PRR/ROR statistics;
- a sourced temporal benchmark definition with monthly trajectories and controls;
- FastAPI endpoints and a Streamlit research dashboard over complete snapshots;
- dependency-light molecular and protein baseline frameworks with leakage-aware
  splits, metrics, provenance, and model-card artifacts;
- a provider-agnostic evaluation harness for structured tool-using
  life-science workflows;
- unit, integration, API, and benchmark smoke tests in CI.

This repository does **not** claim that an AI system discovers drugs, that a
FAERS association is causal, or that the included baseline frameworks have
achieved real-world predictive performance. No real-data model score is
committed without its source, split, configuration, and generated artifacts.

## Core safety workflow

1. Download an official openFDA FAERS drug-event export.
2. Record its source, covered period, local filename, and SHA-256 checksum in a
   snapshot manifest.
3. Import it atomically into PostgreSQL.
4. Compute report-level disproportionality against that fixed reference
   population.
5. Run historical cases through monthly cutoffs without future reports.
6. Inspect the generated trajectories, uncertainty, controls, and limitations.

See [data provenance](data/README.md), the
[study protocol](docs/pharmacovigilance-study.md), and the
[FAERS data card](docs/data-card-faers.md).

## Setup

Python 3.12 is the tested runtime. With `uv`:

```bash
uv sync --extra dev
docker compose up db -d
uv run pharmascope init-db
```

Copy `data/snapshot-manifest.example.json`, fill it with a downloaded export and
its checksum, then run:

```bash
uv run pharmascope load-snapshot data/snapshot-manifest.json
uv run uvicorn pharmascope.api.main:app --reload --port 8000
uv run streamlit run demo/app.py --server.port 8501
```

Dashboard: `http://localhost:8501`

API documentation: `http://localhost:8000/docs`

The dashboard deliberately refuses to analyze an incomplete or ad hoc reference
population.

## Temporal benchmark

The normalized evaluation extract is documented in `data/README.md`. Run:

```bash
uv run pharmascope benchmark data/derived/faers-pairs.csv
```

Outputs are written under `artifacts/benchmark/` and include per-case monthly
trajectories, first threshold-crossing dates, lead times, and aggregate
classification metrics. `data/benchmark_cases.json` contains five sourced
historical positive cases and five comparator events. Comparator events are not
represented as known-safe causal negatives.

## Connected research tracks

- [Molecular safety](docs/molecular-safety.md): endpoint records, deterministic
  group-aware splitting, hashed fingerprint baseline, calibration and
  applicability-domain analysis.
- [Protein-aware modeling](docs/protein-modeling.md): validated protein–ligand
  records, held-out family/scaffold splits, sequence-composition and ligand
  hashing baseline, ridge regression, and regression metrics.
- [Life-science evaluations](docs/life-science-evals.md): structured tasks,
  tool-call traces, deterministic graders, JSONL I/O, and an explicit synthetic
  smoke suite.

These are auditable baseline implementations, not substitutes for RDKit
Bemis–Murcko scaffolds, pretrained protein language models, or a run on a
licensed scientific dataset.

## Development

```bash
uv run ruff check src tests
uv run pytest -v --cov=pharmascope --cov-report=term-missing
```

Architecture and trust boundaries are documented in
[docs/architecture.md](docs/architecture.md). The
[technical defense guide](docs/interview-guide.md) lists the decisions and
limitations a contributor should be able to explain. The
[portfolio release guide](docs/portfolio-release.md) separates currently
supported claims from experiments and external review that still must happen.

## Safety and intended use

PharmaScope is for research and education. It is not a medical device, clinical
decision-support system, or autonomous regulatory tool. FAERS reports lack
exposure denominators and are subject to missingness, duplication, reporting
bias, and confounding. Signals require expert review and independent evidence.

## License

MIT

