import streamlit as st
import json, os, datetime
from auth import login_gate
from crew import run_alphahire

st.set_page_config(
    page_title="AlphaHire", page_icon="🧠",
    layout="wide", initial_sidebar_state="collapsed"
)
login_gate()

st.markdown("# 🧠 AlphaHire")
st.caption(f"AI-Native Quant Recruitment Engine | Delhi-NCR  ·  Logged in as `{st.session_state.user}`")
st.divider()

DATA_PATH = "mock_data/candidates.json"
with open(DATA_PATH) as f:
    data = json.load(f)

role = data["open_role"]
candidates = data["candidates"]

with st.sidebar:
    st.markdown("### 📋 Open Role")
    st.json(role)
    st.markdown("### 👥 Candidate Pool")
    for c in candidates:
        st.markdown(f"**{c['name']}** · {c['city']} · {c['experience_years']}y exp")
    if st.button("🔓 Logout"):
        st.session_state.authed = False
        st.rerun()

st.markdown("## 🚀 Recruitment Pipeline")
st.markdown("""
| Step | Agent | Task |
|---|---|---|
| 1 | JD Writer | Generate role requirements |
| 2 | Screener | Score & rank all candidates |
| 3 | Scheduler | Book interviews for top 3 |
| 4 | Onboarding Agent | Build 30-day plan for #1 |
| 5 | Assessment Designer | Create quant aptitude test |
""")

if "results" not in st.session_state:
    st.session_state.results = None

if st.button("▶ Run AlphaHire Pipeline", type="primary", use_container_width=True):
    st.session_state.results = None  # clear previous
    with st.status("🤖 Agents running... (5-12 min on local LLM)", expanded=True) as status:
        st.write("🟡 Agent 1 — JD Writer...")
        st.write("🟡 Agent 2 — Candidate Screener...")
        st.write("🟡 Agent 3 — Interview Scheduler...")
        st.write("🟡 Agent 4 — Onboarding Agent...")
        st.write("🟡 Agent 5 — Assessment Designer...")
        try:
            results = run_alphahire(data)
            st.session_state.results = results
            status.update(label="✅ Pipeline complete!", state="complete")
        except Exception as e:
            status.update(label=f"❌ Failed: {e}", state="error")
            st.error(str(e))

if st.session_state.results:
    r = st.session_state.results
    st.divider()
    st.markdown("## 📊 Pipeline Output")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📄 Job Description",
        "🏆 Screening Results",
        "📅 Interview Schedule",
        "🎓 Onboarding Plan",
        "📝 Aptitude Test"
    ])

    def dedup(text: str) -> str:
        """Remove consecutive duplicate paragraphs (3b model repeat fix)."""
        if not text:
            return "—"
        blocks = text.strip().split("\n\n")
        seen, out = [], []
        for b in blocks:
            b = b.strip()
            if b not in seen:
                seen.append(b)
                out.append(b)
        return "\n\n".join(out)

    with tab1:
        st.markdown(dedup(r["jd"]))

    with tab2:
        st.markdown(dedup(r["screening"]))

    with tab3:
        st.markdown(dedup(r["schedule"]))
    with tab4:
        st.markdown(dedup(r["onboarding"]))

    with tab5:
        st.markdown(dedup(r["assessment"]))

    # Save output
    os.makedirs("outputs", exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = f"outputs/run_{ts}.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# AlphaHire Run — {ts}\n\n")
        for k, v in r.items():
            if k != "raw":
                f.write(f"## {k.upper()}\n{v}\n\n")
    st.success(f"✅ Output saved → `{out_path}`")