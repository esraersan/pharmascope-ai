"""FastAPI application for pharmascope-ai."""

from typing import Annotated

import structlog
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from pharmascope.config.database import get_db, test_connection
from pharmascope.ingestion.models import DataSnapshot
from pharmascope.retrieval.pubmed import get_pubmed_context
from pharmascope.signals.calculator import compute_signals, resolve_snapshot_id

logger = structlog.get_logger()
DbSession = Annotated[Session, Depends(get_db)]

app = FastAPI(
    title="pharmascope-ai",
    description="Drug safety intelligence platform — FAERS signal detection",
    version="0.1.0",
)


class DrugRequest(BaseModel):
    drug_name: str
    snapshot_id: str | None = None


class SignalResponse(BaseModel):
    drug_name: str
    event_term: str
    report_count: int
    prr: float
    prr_lower_ci: float
    prr_upper_ci: float
    ror: float
    ror_lower_ci: float
    ror_upper_ci: float
    is_signal: bool
    snapshot_id: str


class PaperResponse(BaseModel):
    pmid: str
    title: str
    authors: str
    journal: str
    pub_date: str
    url: str
    query_event: str | None = None


class AnalysisResponse(BaseModel):
    drug_name: str
    snapshot_id: str
    total_signals: int
    flagged_signals: int
    signals: list[SignalResponse]
    literature: list[PaperResponse]


@app.get("/health")
def health_check():
    db_ok = test_connection()
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "unreachable",
    }


@app.get("/snapshots")
def list_snapshots(db: DbSession):
    """List complete reference populations available for analysis."""
    snapshots = (
        db.query(DataSnapshot)
        .filter_by(is_complete=True)
        .order_by(DataSnapshot.period_end.desc())
        .all()
    )
    return [
        {
            "snapshot_id": snapshot.snapshot_id,
            "period_start": snapshot.period_start,
            "period_end": snapshot.period_end,
            "report_count": snapshot.report_count,
            "sha256": snapshot.sha256,
            "source_url": snapshot.source_url,
        }
        for snapshot in snapshots
    ]


@app.post("/analyze", response_model=AnalysisResponse)
def analyze_drug(request: DrugRequest, db: DbSession):
    """
    Analyze a drug against a fixed FAERS snapshot and retrieve literature.
    """
    drug = request.drug_name.lower().strip()
    if not drug:
        raise HTTPException(status_code=400, detail="drug_name cannot be empty")

    logger.info("analyze_request", drug=drug)

    try:
        snapshot_id = resolve_snapshot_id(db, request.snapshot_id)
        signals = compute_signals(drug, db, snapshot_id=snapshot_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception as e:
        logger.error("signal_computation_failed", drug=drug, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Signal computation failed: {e}",
        ) from e

    # Get flagged events for literature search
    flagged_events = [s.event_term for s in signals if s.is_signal][:5]
    try:
        papers = get_pubmed_context(drug, flagged_events or None, max_per_event=3)
    except Exception as e:
        logger.warning("pubmed_failed", drug=drug, error=str(e))
        papers = []

    response_signals = [
        SignalResponse(
            drug_name=s.drug_name,
            event_term=s.event_term,
            report_count=s.report_count,
            prr=s.prr,
            prr_lower_ci=s.prr_lower_ci,
            prr_upper_ci=s.prr_upper_ci,
            ror=s.ror,
            ror_lower_ci=s.ror_lower_ci,
            ror_upper_ci=s.ror_upper_ci,
            is_signal=s.is_signal,
            snapshot_id=s.snapshot_id,
        )
        for s in signals
    ]

    response_papers = [
        PaperResponse(**p) for p in papers
    ]

    return AnalysisResponse(
        drug_name=drug,
        snapshot_id=snapshot_id,
        total_signals=len(signals),
        flagged_signals=sum(1 for s in signals if s.is_signal),
        signals=response_signals,
        literature=response_papers,
    )
