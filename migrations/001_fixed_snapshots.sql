BEGIN;

CREATE TABLE IF NOT EXISTS data_snapshots (
    snapshot_id VARCHAR(100) PRIMARY KEY,
    source_url VARCHAR(500) NOT NULL,
    sha256 VARCHAR(64) NOT NULL,
    period_start TIMESTAMP NULL,
    period_end TIMESTAMP NULL,
    report_count INTEGER NOT NULL DEFAULT 0,
    is_complete BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE adverse_event_reports
    ADD COLUMN IF NOT EXISTS report_version INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS snapshot_id VARCHAR(100) NOT NULL DEFAULT 'adhoc';

ALTER TABLE drug_event_pairs
    ADD COLUMN IF NOT EXISTS snapshot_id VARCHAR(100) NOT NULL DEFAULT 'adhoc',
    ADD COLUMN IF NOT EXISTS drug_role VARCHAR(30) NOT NULL DEFAULT 'unknown';

ALTER TABLE adverse_event_reports
    DROP CONSTRAINT IF EXISTS adverse_event_reports_report_id_key;
ALTER TABLE adverse_event_reports
    DROP CONSTRAINT IF EXISTS uq_snapshot_report;
ALTER TABLE adverse_event_reports
    ADD CONSTRAINT uq_snapshot_report UNIQUE (snapshot_id, report_id);

CREATE INDEX IF NOT EXISTS ix_adverse_event_reports_snapshot_id
    ON adverse_event_reports (snapshot_id);
CREATE INDEX IF NOT EXISTS ix_drug_event_pairs_snapshot_drug
    ON drug_event_pairs (snapshot_id, drug_name_normalized);

COMMIT;
