"""Streamlit dashboard for pharmascope-ai."""

import streamlit as st
import plotly.express as px
import httpx
import pandas as pd

API_URL = "http://localhost:8000"


def show_literature(papers: list[dict]) -> None:
    """Show PubMed literature section."""
    if not papers:
        return
    st.subheader("📚 Supporting Literature")
    for p in papers:
        with st.expander(f"📄 {p['title'][:100]}"):
            st.markdown(f"**Authors:** {p['authors']}")
            st.markdown(f"**Journal:** {p['journal']}")
            st.markdown(f"**Published:** {p['pub_date']}")
            if p.get('query_event'):
                st.markdown(f"**Related to:** {p['query_event']}")
            st.markdown(f"[View on PubMed]({p['url']})")


st.set_page_config(
    page_title="pharmascope-ai",
    page_icon="💊",
    layout="wide",
)

st.title("💊 pharmascope-ai")
st.markdown("**Drug Safety Intelligence Platform** — FAERS Signal Detection")
st.divider()

col1, col2 = st.columns([3, 1])
with col1:
    drug_name = st.text_input(
        "Enter a drug name",
        placeholder="e.g. rofecoxib, ibuprofen, metformin",
    )
with col2:
    limit = st.slider("Reports to fetch", 50, 500, 100, step=50)

analyze = st.button("🔍 Analyze", type="primary")

if analyze and drug_name:
    with st.spinner(f"Fetching FAERS data and computing signals for {drug_name}..."):
        try:
            response = httpx.post(
                f"{API_URL}/analyze",
                json={"drug_name": drug_name, "limit": limit},
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

    st.subheader("📊 Summary")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Drug-Event Pairs", data["total_signals"])
    m2.metric("Flagged Signals", data["flagged_signals"])
    m3.metric("Top PRR", f"{df['prr'].max():.2f}")
    m4.metric("Top ROR", f"{df['ror'].max():.2f}")

    st.divider()

    st.subheader("🚨 Signal Detection Results")
    df["flagged"] = df["is_signal"].map({True: "🚨 Yes", False: "No"})
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

    st.subheader("📈 Top 15 Signals by PRR")
    top15 = df.head(15).copy()
    top15["color"] = top15["is_signal"].map({True: "Flagged Signal", False: "Below Threshold"})
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

    st.subheader("🔬 PRR vs ROR Comparison")
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
    st.caption("Data source: FDA FAERS via openFDA API | Stats: PRR + ROR with 95% CI")

elif analyze and not drug_name:
    st.warning("Please enter a drug name.")
