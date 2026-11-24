import asyncio
import sqlite3
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agent import answer

DB_PATH = ROOT / "agent_calls.db"

st.set_page_config(page_title="Superloop Internal Help Agent", layout="wide")
st.title("Superloop Internal Help Agent")

left, right = st.columns([2, 1])

with left:
    question = st.text_input("Ask a public-help-article question")
    if st.button("Send") and question.strip():
        with st.spinner("Searching help articles"):
            result = asyncio.run(answer(question))
        st.markdown(result["answer"])
        st.caption(
            f"{len(result['chunk_ids'])} chunk(s) retrieved, {len(result['used_chunk_ids'])} cited, "
            f"{result['input_tokens'] + result['output_tokens']} tokens, "
            f"USD ${result['cost_usd']:.6f}, {result['latency_ms']} ms"
        )

with right:
    st.subheader("Usage and cost")
    if DB_PATH.exists():
        with sqlite3.connect(DB_PATH) as connection:
            row = connection.execute(
                """
                SELECT COUNT(*), COALESCE(SUM(cost_usd), 0),
                       COALESCE(AVG(cost_usd), 0),
                       COALESCE(AVG(latency_ms), 0),
                       COALESCE(SUM(CASE WHEN lower(final_outcome) LIKE 'not covered%'
                                           OR lower(final_outcome) LIKE '%refus%'
                                           OR lower(final_outcome) LIKE '%verification failed%' THEN 1 ELSE 0 END), 0)
                FROM agent_calls
                """
            ).fetchone()
        total_calls, total_cost, cost_per_answer, mean_latency, escalations = row
        st.metric("Total calls", total_calls)
        st.metric("Total cost", f"USD ${total_cost:.6f}")
        st.metric("Cost per answer", f"USD ${cost_per_answer:.6f}")
        st.metric("Mean latency", f"{mean_latency:.0f} ms")
        st.metric("Escalation rate", f"{100 * escalations / total_calls:.1f}%" if total_calls else "0.0%")
    else:
        st.info("No agent calls logged yet.")
