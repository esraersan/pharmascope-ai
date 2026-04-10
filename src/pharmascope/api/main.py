"""FastAPI application for pharmascope-ai."""

import structlog
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from pharmascope.config.database import get_db, test_connection
from pharmascope.ingestion.fetcher import store_reports
from pharmascope.signals.calculator import compute_signals
from pharmascope.retrieval.pubmed import get_pubmed_context

logger = structlog.get_logger()

app = FastAPI(
    title="pharmascope-ai",
    description="Drug safety intelligence platform — FAERS signal detection",
    version="0.1.0",
)


class DrugRequest(BaseModel):
    drug_name: str
    limit: int = 100


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


@app.post("/analyze", response_model=AnalysisResponse)
def analyze_drug(request: DrugRequest, db: Session = Depends(get_db)):
    """
    Fetch FAERS reports for a drug and return PRR/ROR signals + PubMed literature.
    """
    drug = request.drug_name.lower().strip()
    if not drug:
        raise HTTPException(status_code=400, detail="drug_name cannot be empty")

    logger.info("analyze_request", drug=drug)

    try:
        store_reports(drug, db, limit=request.limit)
    except Exception as e:
        logger.error("ingestion_failed", drug=drug, error=str(e))
        raise HTTPException(status_code=502, detail=f"Failed to fetch FAERS data: {e}")

    try:
        signals = compute_signals(drug, db)
    except Exception as e:
        logger.error("signal_computation_failed", drug=drug, error=str(e))
        raise HTTPException(status_code=500, detail=f"Signal computation failed: {e}")

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
        )
        for s in signals
    ]

    response_papers = [
        PaperResponse(**p) for p in papers
    ]

    return AnalysisResponse(
        drug_name=drug,
        total_signals=len(signals),
        flagged_signals=sum(1 for s in signals if s.is_signal),
        signals=response_signals,
        literature=response_papers,
    )
