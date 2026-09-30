# Data provenance

PharmaScope does not commit raw FAERS records. FAERS exports are large and can
change when follow-up reports arrive. Every analysis must therefore reference an
immutable local artifact through a manifest containing:

- a unique `snapshot_id`;
- the FDA source URL and covered dates;
- the local filename;
- a SHA-256 checksum.

Generate a checksum after downloading an official openFDA drug-event export:

```bash
pharmascope checksum data/raw/drug-event-0001-of-0001.json.zip
```

Copy `snapshot-manifest.example.json`, fill in its fields, initialize the
database, and import:

```bash
pharmascope init-db
pharmascope load-snapshot data/snapshot-manifest.json
```

The importer accepts openFDA JSON objects with a `results` array, JSON lists,
JSONL/NDJSON, gzip files, and ZIP archives containing those formats. A snapshot
is exposed to signal analysis only after checksum validation and a complete
transaction.

## Normalized evaluation format

The temporal benchmark can also consume a small, derived CSV with these fields:

```text
report_id,receive_date,drug_name_normalized,event_term_normalized,drug_role
```

Rows represent report-level drug-event observations. Only primary and secondary
suspect drugs enter the primary analysis. Derived extracts must retain their own
source manifest and must never be described as the full FAERS corpus.

`benchmark_cases.json` contains sourced positive cases and comparator events.
The comparator events are not known-safe causal negatives; they test whether the
method indiscriminately flags unrelated event terms.
