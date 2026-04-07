"""Fetch adverse event reports from the openFDA API."""

import httpx
import structlog
from datetime import datetime
from sqlalchemy.orm import Session
from pharmascope.ingestion.models import AdverseEventReport, DrugEventPair

logger = structlog.get_logger()

OPENFDA_URL = "https://api.fda.gov/drug/event.json"


def normalize(text: str) -> str:
    """Lowercase and strip whitespace from a string."""
    return text.lower().strip() if text else ""


def fetch_reports(drug_name: str, limit: int = 100) -> list[dict]:
    """
    Fetch adverse event reports for a drug from openFDA.
    
    Args:
        drug_name: The drug name to search for e.g. 'rofecoxib'
        limit: How many reports to fetch (max 100 per request)
    
    Returns:
        List of raw report dicts from the API
    """
    params = {
        "search": f'patient.drug.medicinalproduct:"{drug_name}"',
        "limit": limit,
    }

    logger.info("fetching_faers_reports", drug=drug_name, limit=limit)

    with httpx.Client(timeout=30) as client:
        response = client.get(OPENFDA_URL, params=params)
        response.raise_for_status()
        data = response.json()

    results = data.get("results", [])
    logger.info("fetched_reports", drug=drug_name, count=len(results))
    return results


def parse_report(raw: dict) -> tuple[dict, list[dict]]:
    """
    Parse a raw openFDA report into structured data.

    Returns:
        A tuple of (report_dict, list of drug_event_pair dicts)
    """
    report_id = raw.get("safetyreportid", "")
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
        for reaction in reactions:
            event_term = reaction.get("reactionmeddrapt", "")
            if not event_term:
                continue
            pairs.append({
                "report_id": report_id,
                "drug_name": drug_name,
                "drug_name_normalized": normalize(drug_name),
                "event_term": event_term,
                "event_term_normalized": normalize(event_term),
            })

    return report, pairs


def store_reports(drug_name: str, db: Session, limit: int = 100) -> int:
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
        report_dict, pairs = parse_report(raw)

        # Skip if already stored
        exists = db.query(AdverseEventReport).filter_by(
            report_id=report_dict["report_id"]
        ).first()
        if exists:
            continue

        report = AdverseEventReport(**report_dict)
        db.add(report)

        for pair_dict in pairs:
            pair = DrugEventPair(**pair_dict)
            db.add(pair)

        stored += 1

    db.commit()
    logger.info("stored_reports", drug=drug_name, count=stored)
    return stored
