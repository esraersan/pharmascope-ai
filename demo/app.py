"""Streamlit dashboard for pharmascope-ai."""

import json
import os
from pathlib import Path

import httpx
import pandas as pd
import plotly.express as px
import streamlit as st

API_URL = os.getenv("PHARMASCOPE_API_URL", "http://localhost:8000")
ARTIFACT_DIR = Path(os.getenv("PHARMASCOPE_ARTIFACT_DIR", "artifacts/benchmark"))


@st.cache_data(ttl=30)
def get_snapshots() -> list[dict]:
    response = httpx.get(f"{API_URL}/snapshots", timeout=10)
    response.raise_for_status()
    return response.json()


def show_literature(papers: list[dict]) -> None:
    """Show PubMed literature section."""
    if not papers:
        return
    st.subheader("Supporting literature")
    for p in papers:
        with st.expander(p["title"][:100]):
            st.markdown(f"**Authors:** {p['authors']}")
            st.markdown(f"**Journal:** {p['journal']}")
            st.markdown(f"**Published:** {p['pub_date']}")
            if p.get('query_event'):
                st.markdown(f"**Related to:** {p['query_event']}")
            st.markdown(f"[View on PubMed]({p['url']})")


st.set_page_config(
    page_title="pharmascope-ai",
    layout="wide",
)

st.title("pharmascope-ai")
st.markdown("**Reproducible pharmacovigilance signal detection**")
st.divider()

try:
    snapshots = get_snapshots()
except Exception as exc:
    st.error(f"Could not load reference snapshots from the API: {exc}")
    st.stop()

if not snapshots:
    st.warning(
        "No complete FAERS snapshot is available. Validate and import a fixed "
        "snapshot before running signal analysis."
    )
    st.code(
        "pharmascope init-db\n"
        "pharmascope load-snapshot data/snapshot-manifest.json"
    )
    st.stop()

snapshot_labels = {
    snapshot["snapshot_id"]: (
        f"{snapshot['snapshot_id']} — "
        f"{snapshot['report_count']:,} reports"
    )
    for snapshot in snapshots
}
col1, col2 = st.columns([2, 2])
with col1:
    drug_name = st.text_input(
        "Drug name",
        placeholder="e.g. rofecoxib",
    )
with col2:
    snapshot_id = st.selectbox(
        "Fixed reference snapshot",
        options=list(snapshot_labels),
        format_func=snapshot_labels.get,
    )

analyze = st.button("Analyze", type="primary")

if analyze and drug_name:
    with st.spinner(f"Computing signals for {drug_name}..."):
        try:
            response = httpx.post(
                f"{API_URL}/analyze",
                json={"drug_name": drug_name, "snapshot_id": snapshot_id},
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            st.error(f"API error: {e}")
            st.stop()

    signals = data["signals"]
    if not signals:
        st.warning("No signals found. Try a different drug or increase report limit.")
        st.stop()

    df = pd.DataFrame(signals)

    st.subheader("Summary")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Drug-Event Pairs", data["total_signals"])
    m2.metric("Flagged Signals", data["flagged_signals"])
    m3.metric("Top PRR", f"{df['prr'].max():.2f}")
    m4.metric("Top ROR", f"{df['ror'].max():.2f}")

    st.divider()

    st.subheader("Signal detection results")
    df["flagged"] = df["is_signal"].map({True: "Yes", False: "No"})
    df_display = df[[
        "event_term", "report_count", "prr", "prr_lower_ci",
        "prr_upper_ci", "ror", "flagged"
    ]].rename(columns={
        "event_term": "Adverse Event",
        "report_count": "Reports",
        "prr": "PRR",
        "prr_lower_ci": "PRR Lower CI",
        "prr_upper_ci": "PRR Upper CI",
        "ror": "ROR",
        "flagged": "Signal?",
    })
    st.dataframe(df_display, use_container_width=True, hide_index=True)

    st.divider()

    st.subheader("Top 15 signals by PRR")
    top15 = df.head(15).copy()
    top15["color"] = top15["is_signal"].map(
        {True: "Flagged Signal", False: "Below Threshold"}
    )
    fig = px.bar(
        top15,
        x="prr",
        y="event_term",
        orientation="h",
        color="color",
        color_discrete_map={
            "Flagged Signal": "#ef4444",
            "Below Threshold": "#94a3b8",
        },
        labels={"prr": "PRR", "event_term": "Adverse Event"},
        title=f"PRR Scores for {drug_name.title()}",
    )
    fig.add_vline(x=2.0, line_dash="dash", line_color="orange",
                  annotation_text="Signal threshold (PRR=2.0)")
    fig.update_layout(yaxis=dict(autorange="reversed"), height=500)
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    st.subheader("PRR vs ROR comparison")
    fig2 = px.scatter(
        df,
        x="prr",
        y="ror",
        size="report_count",
        color="is_signal",
        hover_name="event_term",
        color_discrete_map={True: "#ef4444", False: "#94a3b8"},
        labels={"prr": "PRR", "ror": "ROR", "is_signal": "Signal"},
        title="PRR vs ROR — bubble size = report count",
    )
    fig2.add_hline(y=2.0, line_dash="dash", line_color="orange")
    fig2.add_vline(x=2.0, line_dash="dash", line_color="orange")
    st.plotly_chart(fig2, use_container_width=True)

    show_literature(data.get("literature", []))

    st.divider()
    st.caption(
        f"Reference population: {data['snapshot_id']} | "
        "Suspect-drug reports only | PRR and ROR with 95% confidence intervals"
    )
    st.info(
        "Disproportionality identifies reporting associations, not causation. "
        "Spontaneous reports are affected by under-reporting, stimulated "
        "reporting, missing data, and confounding by indication."
    )

elif analyze and not drug_name:
    st.warning("Please enter a drug name.")

summary_path = ARTIFACT_DIR / "summary.json"
if summary_path.exists():
    st.divider()
    st.header("Retrospective temporal benchmark")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    case_options = {
        case["case_id"]: case for case in summary.get("cases", [])
    }
    if case_options:
        case_id = st.selectbox("Benchmark case", options=list(case_options))
        trajectory_path = ARTIFACT_DIR / f"{case_id}.json"
        if trajectory_path.exists():
            trajectory = pd.DataFrame(
                json.loads(trajectory_path.read_text(encoding="utf-8"))
            )
            trajectory["cutoff"] = pd.to_datetime(trajectory["cutoff"])
            figure = px.line(
                trajectory,
                x="cutoff",
                y=["prr", "prr_lower_ci"],
                labels={"cutoff": "Report cutoff", "value": "Ratio"},
                title=f"Temporal signal trajectory: {case_id}",
            )
            figure.add_hline(
                y=2.0,
                line_dash="dash",
                annotation_text="PRR threshold",
            )
            st.plotly_chart(figure, use_container_width=True)
            selected = case_options[case_id]
            st.caption(
                f"First threshold crossing: "
                f"{selected.get('first_signal_date') or 'not observed'} | "
                f"Regulatory date: "
                f"{selected.get('regulatory_date') or 'control case'}"
            )
