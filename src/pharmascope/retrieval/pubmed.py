"""PubMed semantic search."""

import time
import structlog
import httpx

logger = structlog.get_logger()

PUBMED_SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_SUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"


def search_pubmed(
    drug_name: str,
    event_term: str | None = None,
    max_results: int = 10,
    min_year: int = 2018,
) -> list[dict]:
    """Search PubMed for papers about a drug, optionally filtered by adverse event."""
    if event_term:
        query = f"{drug_name} {event_term} adverse event"
    else:
        query = f"{drug_name} drug safety adverse event"

    logger.info("searching_pubmed", query=query)

    search_params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
        "datetype": "pdat",
        "mindate": str(min_year),
        "maxdate": "2026",
        "sort": "relevance",
    }

    try:
        with httpx.Client(timeout=30) as client:
            response = client.get(PUBMED_SEARCH_URL, params=search_params)
            response.raise_for_status()
            search_data = response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            logger.warning("pubmed_rate_limited", query=query)
            time.sleep(2)
            return []
        raise

    pmids = search_data.get("esearchresult", {}).get("idlist", [])
    if not pmids:
        return []

    time.sleep(0.4)  # respect rate limit between requests

    summary_params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "json",
    }

    with httpx.Client(timeout=30) as client:
        response = client.get(PUBMED_SUMMARY_URL, params=summary_params)
        response.raise_for_status()
        summary_data = response.json()

    papers = []
    uids = summary_data.get("result", {}).get("uids", [])
    for uid in uids:
        paper = summary_data["result"].get(uid, {})
        papers.append({
            "pmid": uid,
            "title": paper.get("title", ""),
            "authors": ", ".join(
                a.get("name", "") for a in paper.get("authors", [])[:3]
            ),
            "journal": paper.get("fulljournalname", ""),
            "pub_date": paper.get("pubdate", ""),
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
        })

    logger.info("pubmed_results", count=len(papers))
    return papers


def get_pubmed_context(
    drug_name: str,
    top_events: list[str] | None = None,
    max_per_event: int = 2,
) -> list[dict]:
    """Get PubMed papers for a drug and its top flagged events."""
    all_papers = []
    seen_pmids = set()

    if not top_events:
        return search_pubmed(drug_name, max_results=5)

    for event in top_events[:3]:  # limit to 3 events to avoid rate limiting
        papers = search_pubmed(drug_name, event, max_results=max_per_event)
        for paper in papers:
            if paper["pmid"] not in seen_pmids:
                paper["query_event"] = event
                all_papers.append(paper)
                seen_pmids.add(paper["pmid"])
        time.sleep(0.5)  # pause between event searches

    return all_papers
