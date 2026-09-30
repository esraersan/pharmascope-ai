# Technical defense guide

Use this document to test understanding, not to memorize a sales pitch.

## Pharmacovigilance

Be able to derive PRR and ROR from the four contingency cells and explain why
their confidence intervals are calculated on the log scale. Explain why a
fixed reference population changes the meaning of the denominator and why
query-time ingestion made the earlier implementation invalid.

Explain each FAERS drug role, follow-up report handling, MedDRA preferred terms,
the difference between a reporting association and causality, and the effects
of notoriety bias, confounding by indication, missing exposure denominators, and
multiple testing.

## Molecular machine learning

Explain why a random molecular split can overestimate generalization, what a
true Bemis–Murcko scaffold split requires, why a fingerprint baseline is useful,
and how calibration and applicability domain affect decisions. State clearly
which current utilities are dependency-light educational baselines and which
experiments still require RDKit and a sourced endpoint dataset.

## Protein-aware modeling

Explain the distinction between sequence-composition features and pretrained
protein embeddings. Describe why holding out protein families and ligand
scaffolds is harder than a random pair split and what biological generalization
each split tests.

## Scientific agents

Explain why deterministic tools and reference tasks come before orchestration.
Distinguish factual answer accuracy, evidence support, valid tool choice,
executable analysis correctness, and appropriate refusal. Be prepared to show a
failure trace and explain how the grader avoids rewarding fluent unsupported
answers.

## Evidence checklist

For every result, answer:

1. What exact scientific question was fixed before modeling?
2. Where did every datum and label come from?
3. What information could leak across the split or temporal cutoff?
4. Which simple baseline must the method beat?
5. How is uncertainty represented?
6. What failed, and what changed because of that failure?
7. Which conclusion is supported, and which tempting conclusion is not?
