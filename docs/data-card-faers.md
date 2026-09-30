# FAERS data card

## Source

The FDA Adverse Event Reporting System contains spontaneous adverse-event and
medication-error reports submitted to FDA. PharmaScope accepts official openFDA
drug-event exports and records the exact source URL, covered period, and SHA-256
checksum for each imported snapshot.

## Intended use

- retrospective pharmacovigilance method evaluation;
- report-level disproportionality screening;
- education about reproducible safety-signal workflows.

## Out-of-scope use

- estimating event incidence or absolute risk;
- diagnosing a patient or changing treatment;
- ranking drugs as safe or unsafe;
- inferring that a drug caused a reported event;
- autonomous regulatory or clinical decisions.

## Unit of analysis

The counting unit is a unique FDA safety report after retaining its latest
available follow-up version. Drug-event observations preserve FDA drug role.
The primary analysis includes primary and secondary suspect products only.

## Known limitations

Reports can be incomplete, duplicated across imperfectly linked cases, biased by
publicity, and affected by under-reporting or stimulated reporting. Exposure
denominators are absent. Drug names require synonym normalization, and MedDRA
terms can be analyzed at different hierarchy levels. Concomitant disease and
indication can confound associations.

## Provenance requirements

Results are valid only when accompanied by:

1. snapshot manifest and checksum;
2. normalization and follow-up-version policy;
3. benchmark case version;
4. code revision and runtime configuration;
5. generated trajectory and summary artifacts.

Raw records are not committed to this repository.
