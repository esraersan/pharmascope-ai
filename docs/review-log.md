# External review log

No external scientific review has been completed yet. Do not represent this
repository as peer reviewed.

When a pharmacovigilance, cheminformatics, computational-biology, or ML
practitioner reviews an artifact, record:

- reviewer expertise and date;
- commit or release reviewed;
- concrete criticism;
- whether the criticism was accepted, rejected, or needs evidence;
- code, data, or documentation change;
- unresolved risk.

## Requested review questions

### Pharmacovigilance

- Are follow-up reports, drug roles, and report-level contingency cells handled
  correctly?
- Are benchmark dates and comparator cases defensible?
- Which sensitivity analysis is necessary before publishing a result?

### Cheminformatics

- Are molecule standardization, scaffold splitting, and applicability-domain
  claims correct?
- Does the baseline comparison answer a useful safety question?

### Computational biology

- Does the protein-family holdout measure the stated generalization?
- Are sequence and structure metadata used without biological leakage?

### ML evaluation

- Can every agent score be independently reproduced?
- Do graders reward evidence and valid computation rather than surface form?
