"""FastAPI application for pharmascope-ai."""

import time
import structlog
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from pharmascope.config.database import get_db, test_connection
from pharmascope.ingestion.fetcher import store_reports
from pharmascope.signals.calculator import compute_signals, SignalScore

logger = structlog.get_logger()

app = FastAPI(
    title="pharmascope-ai",
    description="Drug safety intelligence platform — FAERS signal detection + LLM synthesis",
    version="0.1.0",
)


# ---------- Request / Response Models ----------

class AnalyzeRequest(BaseModel):
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


class AnalyzeResponse(BaseModel):
    drug_name: str
    total_signals: int
    flagged_signals: int
    latency_ms: float
    signals: list[SignalResponse]


# ---------- Endpoints ----------

@app.get("/health")
def health():
    """Check API and database are alive."""
    db_ok = test_connection()
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "unreachable",
    }


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest, db: Session = Depends(get_db)):
    """
    Fetch FAERS reports for a drug and return PRR/ROR signals.

    Args:
        request: Drug name and optional report limit

    Returns:
        Ranked list of drug-event signals with PRR/ROR scores
    """
    start = time.time()
    drug = request.drug_name.lower().strip()

    if not drug:
        raise HTTPException(status_code=400, detail="drug_name cannot be empty")

    logger.info("analyze_request", drug=drug, limit=request.limit)

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

    latency_ms = round((time.time() - start) * 1000, 2)

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

    logger.info(
        "analyze_complete",
        drug=drug,
        total=len(signals),
        flagged=sum(1 for s in signals if s.is_signal),
        latency_ms=latency_ms,
    )

    return AnalyzeResponse(
        drug_name=drug,
        total_signals=len(signals),
        flagged_signals=sum(1 for s in signals if s.is_signal),
        latency_ms=latency_ms,
        signals=response_signals,
    )
