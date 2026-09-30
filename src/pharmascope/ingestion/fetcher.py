"""Fetch and normalize adverse event reports from the openFDA API."""

from datetime import datetime

import httpx
import structlog
from sqlalchemy.orm import Session

from pharmascope.ingestion.models import AdverseEventReport, DrugEventPair

logger = structlog.get_logger()

OPENFDA_URL = "https://api.fda.gov/drug/event.json"
OPENFDA_PAGE_SIZE = 100
DRUG_ROLES = {
    "1": "primary_suspect",
    "2": "secondary_suspect",
    "3": "concomitant",
    "4": "interacting",
}


def normalize(text: str) -> str:
    """Lowercase and strip whitespace from a string."""
    return text.lower().strip() if text else ""


def fetch_reports(drug_name: str, limit: int = 100) -> list[dict]:
    """
    Fetch adverse event reports for a drug from openFDA.
    
    Args:
        drug_name: The drug name to search for e.g. 'rofecoxib'
        limit: Total number of reports to fetch across paginated requests.
    
    Returns:
        List of raw report dicts from the API
    """
    logger.info("fetching_faers_reports", drug=drug_name, limit=limit)
    if limit < 1:
        return []

    escaped_name = drug_name.replace('"', r"\"")
    results: list[dict] = []
    with httpx.Client(timeout=30) as client:
        while len(results) < limit:
            page_size = min(OPENFDA_PAGE_SIZE, limit - len(results))
            params = {
                "search": f'patient.drug.medicinalproduct:"{escaped_name}"',
                "limit": page_size,
                "skip": len(results),
            }
            response = client.get(OPENFDA_URL, params=params)
            response.raise_for_status()
            page = response.json().get("results", [])
            results.extend(page)
            if len(page) < page_size:
                break

    # The API can contain multiple follow-up versions. Retain only the newest
    # version for each safety report before it reaches persistence or analysis.
    latest: dict[str, dict] = {}
    for report in results:
        report_id = str(report.get("safetyreportid", ""))
        if not report_id:
            continue
        version = int(report.get("safetyreportversion") or 1)
        previous = latest.get(report_id)
        previous_version = (
            int(previous.get("safetyreportversion") or 1) if previous else 0
        )
        if version >= previous_version:
            latest[report_id] = report

    results = list(latest.values())
    logger.info("fetched_reports", drug=drug_name, count=len(results))
    return results


def parse_report(raw: dict, snapshot_id: str = "adhoc") -> tuple[dict, list[dict]]:
    """
    Parse a raw openFDA report into structured data.

    Returns:
        A tuple of (report_dict, list of drug_event_pair dicts)
    """
    report_id = raw.get("safetyreportid", "")
    report_version = int(raw.get("safetyreportversion") or 1)
    receive_date_str = raw.get("receivedate", "")

    try:
        receive_date = datetime.strptime(receive_date_str, "%Y%m%d")
    except (ValueError, TypeError):
        receive_date = None

    reporter_type = str(raw.get("primarysource", {}).get("qualification", ""))
    
    outcomes = raw.get("serious", "")
    outcome = "serious" if str(outcomes) == "1" else "non-serious"

    patient = raw.get("patient", {})
    drugs = patient.get("drug", [])
    reactions = patient.get("reaction", [])

    primary_drug = ""
    if drugs:
        primary_drug = drugs[0].get("medicinalproduct", "")

    report = {
        "report_id": report_id,
        "report_version": report_version,
        "snapshot_id": snapshot_id,
        "receive_date": receive_date,
        "reporter_type": reporter_type,
        "outcome": outcome,
        "primary_drug": primary_drug,
    }

    pairs = []
    for drug in drugs:
        drug_name = drug.get("medicinalproduct", "")
        if not drug_name:
            continue
        drug_role = DRUG_ROLES.get(
            str(drug.get("drugcharacterization", "")),
            "unknown",
        )
        for reaction in reactions:
            event_term = reaction.get("reactionmeddrapt", "")
            if not event_term:
                continue
            pairs.append({
                "report_id": report_id,
                "snapshot_id": snapshot_id,
                "drug_name": drug_name,
                "drug_name_normalized": normalize(drug_name),
                "drug_role": drug_role,
                "event_term": event_term,
                "event_term_normalized": normalize(event_term),
            })

    return report, pairs


def store_reports(
    drug_name: str,
    db: Session,
    limit: int = 100,
    snapshot_id: str = "adhoc",
) -> int:
    """
    Fetch and store FAERS reports for a drug.

    Args:
        drug_name: Drug to search for
        db: Database session
        limit: Number of reports to fetch

    Returns:
        Number of reports stored
    """
    raw_reports = fetch_reports(drug_name, limit)
    stored = 0

    for raw in raw_reports:
        report_dict, pairs = parse_report(raw, snapshot_id=snapshot_id)

        existing = db.query(AdverseEventReport).filter_by(
            report_id=report_dict["report_id"],
            snapshot_id=snapshot_id,
        ).first()
        if existing:
            if existing.report_version >= report_dict["report_version"]:
                continue
            # FDA follow-ups supersede earlier versions. Remove stale pairs so
            # one safety report contributes at most once to every count.
            db.query(DrugEventPair).filter_by(
                report_id=report_dict["report_id"],
                snapshot_id=snapshot_id,
            ).delete()
            for key, value in report_dict.items():
                setattr(existing, key, value)
        else:
            report = AdverseEventReport(**report_dict)
            db.add(report)

        unique_pairs = {
            (
                pair["drug_name_normalized"],
                pair["drug_role"],
                pair["event_term_normalized"],
            ): pair
            for pair in pairs
        }
        for pair_dict in unique_pairs.values():
            pair = DrugEventPair(**pair_dict)
            db.add(pair)

        stored += 1

    db.commit()
    logger.info("stored_reports", drug=drug_name, count=stored)
    return stored
