"""Tests for deterministic FAERS report normalization."""

from pharmascope.ingestion.fetcher import parse_report


def test_parse_report_keeps_drug_roles_and_deduplicates_later():
    raw = {
        "safetyreportid": "100",
        "safetyreportversion": "2",
        "receivedate": "20040131",
        "serious": "1",
        "patient": {
            "drug": [
                {
                    "medicinalproduct": "Vioxx",
                    "drugcharacterization": "1",
                },
                {
                    "medicinalproduct": "Aspirin",
                    "drugcharacterization": "3",
                },
            ],
            "reaction": [{"reactionmeddrapt": "Myocardial infarction"}],
        },
    }

    report, pairs = parse_report(raw, snapshot_id="faers-test")

    assert report["report_version"] == 2
    assert report["snapshot_id"] == "faers-test"
    assert {pair["drug_role"] for pair in pairs} == {
        "primary_suspect",
        "concomitant",
    }
    assert all(pair["snapshot_id"] == "faers-test" for pair in pairs)


def test_parse_report_handles_missing_dates_and_unknown_roles():
    raw = {
        "safetyreportid": "101",
        "receivedate": "not-a-date",
        "patient": {
            "drug": [{"medicinalproduct": "Example", "drugcharacterization": "9"}],
            "reaction": [{"reactionmeddrapt": "Headache"}],
        },
    }

    report, pairs = parse_report(raw)

    assert report["receive_date"] is None
    assert pairs[0]["drug_role"] == "unknown"
