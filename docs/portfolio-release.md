# Portfolio release guide

## One-sentence description

PharmaScope is a reproducible scientific-ML portfolio that starts with
report-level pharmacovigilance, adds leakage-aware molecular and protein
baselines, and turns the workflows into verifiable life-science agent tasks.

## Demonstration sequence

1. Show the snapshot manifest and explain why the former query-dependent
   denominator invalidated PRR/ROR.
2. Trace one safety report through follow-up handling, drug roles, a contingency
   table, confidence intervals, and a monthly benchmark trajectory.
3. Show the molecular split and explain why lexical grouping is only a
   dependency-light baseline, not a true chemical scaffold.
4. Show the protein family/ligand group connected-component split and explain
   the generalization question.
5. Run one life-science evaluator response and show that wrong-source citations
   and unsupported causal claims fail deterministically.
6. End with negative results, limitations, and the next experiment requiring a
   real sourced dataset.

## Release evidence

Before describing a release as research-ready, attach:

- clean test and lint output;
- data manifest and checksum;
- generated benchmark summary and trajectories;
- exact model/evaluation configuration;
- data and model cards;
- code revision;
- review-log entries for any external scientific review.

## Claims that are currently supportable

- The safety statistics, importer, benchmark machinery, baseline utilities, and
  deterministic graders are implemented and tested.
- The project enforces complete FAERS snapshots and leakage-aware group
  boundaries.
- The repository contains no fabricated real-data performance result.

## Claims that are not currently supportable

- A historical FAERS signal was detected before a regulator acted.
- A molecular or protein model outperforms a published baseline.
- A particular language model is reliable for life-science research.
- The project has been externally reviewed or peer reviewed.
- The software is suitable for clinical or regulatory decisions.

## Publication checklist

- Run the real FAERS benchmark from a documented snapshot.
- Run molecular and protein experiments on licensed, sourced datasets.
- Populate model cards with observed results and failure analysis.
- Obtain the domain reviews requested in `docs/review-log.md`.
- Correct issues and record them in the review log.
- Only then tag a release, record a demo, and publish the technical report.

The current repository is prepared for these steps, but this document does not
pretend that external reviews or real-data experiments have already happened.
