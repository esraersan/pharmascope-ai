# Retrospective FAERS signal benchmark

## Research question

For historically documented drug–event safety problems, when does a standard
reporting-disproportionality rule first cross its alert threshold relative to a
sourced regulatory date?

## Why this question matters

FAERS is a spontaneous-reporting system. It can surface unusual reporting
patterns, but it does not estimate incidence and cannot establish causality.
The useful, testable claim is therefore narrower: whether a reproducible method
can surface a reporting association early enough to warrant investigation.

## Data contract

The primary analysis uses an immutable, checksummed FAERS snapshot. Each
normalized observation contains a safety-report identifier, receipt date,
normalized drug name, MedDRA preferred term, and drug role. Only primary and
secondary suspect roles enter the main contingency table. FDA follow-up versions
replace earlier versions.

The repository does not distribute raw FAERS data. See `data/README.md` for the
manifest and normalized extract contracts.

## Methods

At every month-end cutoff, PharmaScope constructs report-level cells:

- `a`: target drug and target event;
- `b`: another suspect drug and target event;
- `c`: target drug and another event;
- `d`: another suspect drug and another event.

It computes PRR and ROR with a 0.5 Haldane correction and log-scale 95%
confidence intervals. The preregistered signal rule is at least three joint
reports, PRR at least 2, and PRR lower confidence bound above 1. An IC-like
smoothed observed-to-expected ratio is reported as a transparent comparator; it
is not represented as the proprietary WHO-UMC BCPNN implementation.

## Evaluation

`data/benchmark_cases.json` defines sourced historical cases and within-drug
comparator events. The comparator events are not known-safe causal negatives.
Reported outputs include first threshold-crossing date, lead time to the sourced
regulatory date, precision, recall, and every monthly trajectory.

Run:

```bash
pharmascope benchmark data/derived/faers-pairs.csv
```

Generated files are written to `artifacts/benchmark/` and intentionally ignored
until they are created from a documented snapshot. This repository does not
include fabricated scores.

## Leakage controls

- The reference population is fixed before analysis.
- Time cutoffs exclude reports received after the simulated analysis date.
- Follow-up versions do not count as independent reports.
- Drug roles are retained; concomitant products are excluded from the primary
  analysis.
- Benchmark definitions and regulatory dates are versioned separately from
  generated output.

## Limitations

FAERS has duplicate-report, missingness, notoriety, stimulated-reporting, and
confounding-by-indication problems. Drug-name normalization and MedDRA hierarchy
handling remain important sources of error. Threshold crossing is a triage
signal, not a causal conclusion. A robust study should add sensitivity analyses
for role definitions, deduplication policy, event hierarchy, minimum counts, and
multiple testing.

## Results status

No real-data benchmark result is committed yet. A result is reportable only
after its source snapshot, checksum, configuration, generated trajectories, and
clean-run command are available together.
# Retrospective FAERS signal benchmark

## Research question

For historically documented drug–event safety problems, when does a standard
reporting-disproportionality rule first cross its alert threshold relative to a
sourced regulatory date?

## Why this question matters

FAERS is a spontaneous-reporting system. It can surface unusual reporting
patterns, but it does not estimate incidence and cannot establish causality.
The useful, testable claim is therefore narrower: whether a reproducible method
can surface a reporting association early enough to warrant investigation.

## Data contract

The primary analysis uses an immutable, checksummed FAERS snapshot. Each
normalized observation contains a safety-report identifier, receipt date,
normalized drug name, MedDRA preferred term, and drug role. Only primary and
secondary suspect roles enter the main contingency table. FDA follow-up versions
replace earlier versions.

The repository does not distribute raw FAERS data. See `data/README.md` for the
manifest and normalized extract contracts.

## Methods

At every month-end cutoff, PharmaScope constructs report-level cells:

- `a`: target drug and target event;
- `b`: another suspect drug and target event;
- `c`: target drug and another event;
- `d`: another suspect drug and another event.

It computes PRR and ROR with a 0.5 Haldane correction and log-scale 95%
confidence intervals. The preregistered signal rule is at least three joint
reports, PRR at least 2, and PRR lower confidence bound above 1. An IC-like
smoothed observed-to-expected ratio is reported as a transparent comparator; it
is not represented as the proprietary WHO-UMC BCPNN implementation.

## Evaluation

`data/benchmark_cases.json` defines sourced historical cases and within-drug
comparator events. The comparator events are not known-safe causal negatives.
Reported outputs include first threshold-crossing date, lead time to the sourced
regulatory date, precision, recall, and every monthly trajectory.

Run:

```bash
pharmascope benchmark data/derived/faers-pairs.csv
```

Generated files are written to `artifacts/benchmark/` and intentionally ignored
until they are created from a documented snapshot. This repository does not
include fabricated scores.

## Leakage controls

- The reference population is fixed before analysis.
- Time cutoffs exclude reports received after the simulated analysis date.
- Follow-up versions do not count as independent reports.
- Drug roles are retained; concomitant products are excluded from the primary
  analysis.
- Benchmark definitions and regulatory dates are versioned separately from
  generated output.

## Limitations

FAERS has duplicate-report, missingness, notoriety, stimulated-reporting, and
confounding-by-indication problems. Drug-name normalization and MedDRA hierarchy
handling remain important sources of error. Threshold crossing is a triage
signal, not a causal conclusion. A robust study should add sensitivity analyses
for role definitions, deduplication policy, event hierarchy, minimum counts, and
multiple testing.

## Results status

No real-data benchmark result is committed yet. A result is reportable only
after its source snapshot, checksum, configuration, generated trajectories, and
clean-run command are available together.
