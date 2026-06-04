import streamlit as st
import json, os, datetime, re
from auth import login_gate
from crew import run_alphahire

st.set_page_config(
    page_title="AlphaHire", page_icon="⚡",
    layout="wide", initial_sidebar_state="collapsed"
)

login_gate()

# ── Global CSS ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&family=DM+Serif+Display&display=swap');

/* ── Base ── */
html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
    background-color: #0d0f14;
    color: #e8eaf0;
}

.main .block-container {
    padding: 0 2.5rem 3rem 2.5rem;
    max-width: 1200px;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #0d0f14; }
::-webkit-scrollbar-thumb { background: #2e3340; border-radius: 10px; }

/* ── Topbar ── */
.topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1.4rem 0 1.2rem 0;
    border-bottom: 1px solid #1e2230;
    margin-bottom: 2rem;
}
.topbar-logo {
    display: flex;
    align-items: center;
    gap: 0.7rem;
}
.topbar-icon {
    width: 36px; height: 36px;
    background: linear-gradient(135deg, #f5a623, #e07b00);
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1rem; font-weight: 800; color: #0d0f14;
    font-family: 'DM Serif Display', serif;
    box-shadow: 0 0 16px rgba(245,166,35,0.3);
}
.topbar-title {
    font-size: 1.5rem;
    font-weight: 700;
    letter-spacing: -0.5px;
    color: #ffffff;
}
.topbar-title span {
    color: #f5a623;
}
.session-badge {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    background: #1a1d27;
    border: 1px solid #2e3340;
    color: #7a8299;
    padding: 0.3rem 0.75rem;
    border-radius: 20px;
}

/* ── Section headers ── */
.section-label {
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #f5a623;
    margin-bottom: 0.8rem;
}
.section-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: #e8eaf0;
    margin-bottom: 1.2rem;
}

/* ── Cards ── */
.card {
    background: #13151e;
    border: 1px solid #1e2230;
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
}

/* ── Dataframe override ── */
[data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #1e2230 !important;
}

/* ── Pipeline steps ── */
.pipeline-grid {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 0.8rem;
    margin-bottom: 1.5rem;
}
.pipeline-step {
    background: #13151e;
    border: 1px solid #1e2230;
    border-radius: 10px;
    padding: 1rem 0.9rem;
    position: relative;
    transition: border-color 0.2s;
}
.pipeline-step:hover {
    border-color: #f5a623;
}
.step-num {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    color: #f5a623;
    font-weight: 500;
    margin-bottom: 0.4rem;
}
.step-icon {
    font-size: 1.4rem;
    margin-bottom: 0.5rem;
    display: block;
}
.step-agent {
    font-size: 0.85rem;
    font-weight: 600;
    color: #e8eaf0;
    margin-bottom: 0.25rem;
}
.step-task {
    font-size: 0.75rem;
    color: #5a6278;
    line-height: 1.4;
}
.step-connector {
    position: absolute;
    right: -0.5rem;
    top: 50%;
    transform: translateY(-50%);
    color: #2e3340;
    font-size: 0.8rem;
    z-index: 2;
}

/* ── Run button ── */
[data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, #f5a623, #e07b00) !important;
    color: #0d0f14 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    letter-spacing: 0.02em !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 0.75rem 2rem !important;
    box-shadow: 0 4px 20px rgba(245,166,35,0.25) !important;
    transition: all 0.2s !important;
}
[data-testid="stButton"] > button[kind="primary"]:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 28px rgba(245,166,35,0.4) !important;
}

/* ── Status box ── */
[data-testid="stStatusWidget"] {
    background: #13151e !important;
    border: 1px solid #1e2230 !important;
    border-radius: 10px !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.8rem !important;
}

/* ── Agent checklist ── */
.agent-item {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.6rem 0.9rem;
    background: #0d0f14;
    border-radius: 7px;
    margin-bottom: 0.4rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    color: #7a8299;
    border: 1px solid #1a1d27;
}
.agent-spinner {
    width: 10px; height: 10px;
    border-radius: 50%;
    background: #f5a623;
    animation: pulse 1s infinite;
}
@keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.4; transform: scale(0.85); }
}

/* ── Tabs ── */
[data-baseweb="tab-list"] {
    background: #13151e !important;
    border-bottom: 1px solid #1e2230 !important;
    border-radius: 10px 10px 0 0 !important;
    gap: 0 !important;
    padding: 0 0.5rem !important;
}
[data-baseweb="tab"] {
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    color: #5a6278 !important;
    padding: 0.75rem 1.2rem !important;
    border-bottom: 2px solid transparent !important;
}
[aria-selected="true"][data-baseweb="tab"] {
    color: #f5a623 !important;
    border-bottom: 2px solid #f5a623 !important;
    background: transparent !important;
}
[data-baseweb="tab-panel"] {
    background: #13151e !important;
    border: 1px solid #1e2230 !important;
    border-top: none !important;
    border-radius: 0 0 10px 10px !important;
    padding: 1.5rem !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.88rem !important;
    line-height: 1.7 !important;
    color: #c5c9d6 !important;
}

/* ── Bar chart ── */
[data-testid="stVegaLiteChart"] {
    background: #13151e !important;
    border-radius: 10px !important;
    border: 1px solid #1e2230 !important;
    padding: 1rem !important;
}

/* ── Download button ── */
[data-testid="stDownloadButton"] > button {
    background: transparent !important;
    border: 1px solid #f5a623 !important;
    color: #f5a623 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    border-radius: 8px !important;
    transition: all 0.2s !important;
}
[data-testid="stDownloadButton"] > button:hover {
    background: rgba(245,166,35,0.1) !important;
}

/* ── Success alert ── */
[data-testid="stAlert"] {
    background: #0f1a0f !important;
    border: 1px solid #1e3a1e !important;
    border-radius: 8px !important;
    color: #5db85d !important;
    font-size: 0.82rem !important;
    font-family: 'JetBrains Mono', monospace !important;
}

/* ── Divider ── */
hr {
    border-color: #1e2230 !important;
    margin: 1.5rem 0 !important;
}

/* ── Score chart label ── */
.score-header {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    margin-bottom: 0.8rem;
}
.score-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: #f5a623;
}
</style>
""", unsafe_allow_html=True)


# ── Topbar ─────────────────────────────────────────────────
st.markdown(f"""
<div class="topbar">
    <div class="topbar-logo">
        <div class="topbar-icon">A</div>
        <span class="topbar-title">Alpha<span>Hire</span></span>
    </div>
    <span class="session-badge">⬤ &nbsp;{st.session_state.user}</span>
</div>
""", unsafe_allow_html=True)


# ── Load data ──────────────────────────────────────────────
with open("mock_data/candidates.json") as f:
    data = json.load(f)

role = data["open_role"]
candidates = data["candidates"]


# ── Candidate Pool ─────────────────────────────────────────
st.markdown('<p class="section-label">Talent Intelligence</p>', unsafe_allow_html=True)
st.markdown('<p class="section-title">Candidate Pool &nbsp;<span style="color:#5a6278;font-weight:400;font-size:0.85rem;">Quant Researcher &mdash; AI R&D</span></p>', unsafe_allow_html=True)
import pandas as pd
cdf = pd.DataFrame([{
    "Name": c["name"],
    "City": c["city"],
    "Exp": f"{c['experience_years']}y",
    "Education": c["education"],
    "Previous Role": c["prev_role"],
    "GPA": c["gpa"]
} for c in candidates])
st.dataframe(
    cdf,
    use_container_width=True,
    hide_index=True,
    column_config={
        "GPA": st.column_config.NumberColumn(format="%.1f"),
        "Exp": st.column_config.TextColumn(width="small"),
    }
)

# ── Add/Remove ─────────────────────────────────────────────
with st.expander("Manage Candidates"):
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Add Candidate**")
        new_name = st.text_input("Full Name")
        new_city = st.selectbox("City", ["Delhi", "Noida", "Gurugram", "Faridabad", "Ghaziabad","Bengaluru","Hyderabad","Mumbai","Chennai"], index=0)
        new_exp  = st.number_input("Experience (years)", min_value=0, max_value=20, value=2)
        new_edu  = st.text_input("Education", placeholder="e.g. B.Tech IIT Delhi")
        new_role = st.text_input("Previous Role", placeholder="e.g. Quant Analyst, XYZ")
        new_gpa  = st.number_input("GPA", min_value=0.0, max_value=10.0, value=8.0, step=0.1)
        new_skills = st.text_input("Skills (comma separated)", placeholder="Python, statistics, backtesting")

        if st.button("Add Candidate", use_container_width=True):
            if new_name and new_edu:
                new_candidate = {
                    "id": f"C00{len(data['candidates'])+1}",
                    "name": new_name,
                    "city": new_city,
                    "skills": [s.strip() for s in new_skills.split(",") if s.strip()],
                    "experience_years": int(new_exp),
                    "education": new_edu,
                    "prev_role": new_role,
                    "gpa": float(new_gpa)
                }
                data["candidates"].append(new_candidate)
                with open("mock_data/candidates.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                st.success(f"{new_name} added.")
                st.rerun()
            else:
                st.error("Name and Education are required.")

    with col2:
        st.markdown("**Remove Candidate**")
        names = [c["name"] for c in data["candidates"]]
        to_remove = st.selectbox("Select candidate", names)
        if st.button("Remove", use_container_width=True):
            data["candidates"] = [c for c in data["candidates"] if c["name"] != to_remove]
            with open("mock_data/candidates.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            st.success(f"{to_remove} removed.")
            st.rerun()

st.markdown("<br>", unsafe_allow_html=True)


# ── Pipeline ───────────────────────────────────────────────
st.markdown('<p class="section-label">Automation</p>', unsafe_allow_html=True)
st.markdown('<p class="section-title">Recruitment Pipeline</p>', unsafe_allow_html=True)

steps = [
    ("01", "", "JD Writer", "Generate role requirements & scoring rubric"),
    ("02", "", "Screener", "Score & rank all candidates"),
    ("03", "", "Scheduler", "Book interviews for shortlist"),
    ("04", "", "Onboarding", "Build 30-day plan for top hire"),
    ("05", "", "Assessor", "Create quantitative aptitude test"),
]

cols = st.columns(5)
for i, (num, icon, agent, task) in enumerate(steps):
    with cols[i]:
        st.markdown(f"""
        <div class="pipeline-step">
            <div class="step-num">STEP {num}</div>
            <div class="step-agent">{agent}</div>
            <div class="step-task">{task}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

if "results" not in st.session_state:
    st.session_state.results = None

if st.button("⚡  Run Full Pipeline", type="primary", use_container_width=True):
    st.session_state.results = None
    with st.status("Agents running", expanded=True) as status:
        agent_labels = [
            "Agent 01 — JD Writer",
            "Agent 02 — Candidate Screener",
            "Agent 03 — Interview Scheduler",
            "Agent 04 — Onboarding Agent",
            "Agent 05 — Assessment Designer",
        ]
        for label in agent_labels:
            st.markdown(f"""
            <div class="agent-item">
                <div class="agent-spinner"></div>
                {label}
            </div>
            """, unsafe_allow_html=True)
        try:
            results = run_alphahire(data)
            st.session_state.results = results
            status.update(label="Pipeline complete", state="complete")
        except Exception as e:
            status.update(label=f"Pipeline failed: {e}", state="error")
            st.error(str(e))


# ── Results ────────────────────────────────────────────────
if st.session_state.results:
    r = st.session_state.results
    st.divider()
    if st.button("Clear Results"):
        st.session_state.results = None
        st.rerun()

    # Score chart
    scores = {}
    for line in r["screening"].split("\n"):
        for c in candidates:
            if c["name"] in line:
                nums = re.findall(r'\b(\d{2,3})\b', line)
                if nums:
                    score = int(nums[0])
                    if 0 <= score <= 100:
                        scores[c["name"]] = score

    if scores:
        st.markdown('<p class="section-label">Analysis</p>', unsafe_allow_html=True)

        col1, col2 = st.columns([1.4, 1])

        with col1:
            st.markdown('<p class="section-title">Candidate Scores</p>', unsafe_allow_html=True)
            chart_df = pd.DataFrame(
                list(scores.items()), columns=["Candidate", "Score"]
            ).sort_values("Score", ascending=False)
            st.bar_chart(chart_df.set_index("Candidate"), height=200, color="#f5a623")

        with col2:
            st.markdown('<p class="section-title">Skill Match vs Role</p>', unsafe_allow_html=True)
            required = set(role["required_skills"])
            match_data = []
            for c in candidates:
                if c["name"] in scores:
                    has = set(s.lower() for s in c["skills"])
                    req = set(s.lower() for s in required)
                    matched = len(has & req)
                    total = len(req)
                    pct = round((matched / total) * 100) if total else 0
                    match_data.append({
                        "Candidate": c["name"],
                        "Skills Matched": matched,
                        "Match %": pct
                    })

            if match_data:
                match_df = pd.DataFrame(match_data).sort_values("Match %", ascending=False)
                st.dataframe(
                    match_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Match %": st.column_config.ProgressColumn(
                            "Match %",
                            min_value=0,
                            max_value=100,
                            format="%d%%"
                        )
                    }
                )

        st.markdown("<br>", unsafe_allow_html=True)

    # Output tabs
    st.markdown('<p class="section-label">Output</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-title">Pipeline Results</p>', unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Job Description",
        "Screening",
        "Schedule",
        "Onboarding",
        "Aptitude Test",
    ])

    def dedup(text: str) -> str:
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

    with tab1: st.markdown(dedup(r["jd"]))
    with tab2:
        # take only first 6 data rows max — cuts hallucinated duplicates
        lines = r["screening"].strip().split("\n")
        clean_lines = []
        data_rows = 0
        for line in lines:
            if "|" in line and "---" not in line:
                cells = [c.strip() for c in line.split("|") if c.strip()]
                # skip obviously hallucinated rows (notes in ID field)
                if cells and len(cells) >= 4 and "(" not in cells[0]:
                    if data_rows == 0:
                        clean_lines.append(line)
                        clean_lines.append("|---|---|---|---|---|")
                    elif data_rows <= 6:
                        clean_lines.append("| " + " | ".join(cells[:5]) + " |")
                    data_rows += 1
            elif "---" in line:
                continue
        st.markdown("\n".join(clean_lines) if clean_lines else dedup(r["screening"]))
    with tab3:
        # parse inline pipe table into proper markdown
        raw = r["schedule"].strip()
        if "\n" not in raw and "|" in raw:
            # all on one line — split into rows by double-pipe
            parts = [p.strip() for p in raw.split("|") if p.strip()]
            # group into rows of 4
            rows, row_size = [], 4
            for i in range(0, len(parts), row_size):
                chunk = parts[i:i+row_size]
                if len(chunk) == row_size:
                    rows.append(chunk)
            if rows:
                header = "| " + " | ".join(rows[0]) + " |"
                sep    = "| " + " | ".join(["---"]*row_size) + " |"
                body   = "\n".join("| " + " | ".join(r) + " |" for r in rows[1:])
                st.markdown(f"{header}\n{sep}\n{body}")
            else:
                st.markdown(raw)
        else:
            st.markdown(dedup(raw))
    with tab4:
        # show only first occurrence of each phase
        lines = r["onboarding"].strip().split("\n")
        seen_phases, out = set(), []
        for line in lines:
            if line.strip().startswith("Phase") or "(Days" in line:
                phase_key = line.strip()[:25]
                if phase_key in seen_phases:
                    continue
                seen_phases.add(phase_key)
            out.append(line)
        st.markdown("\n".join(out))
    with tab5:
        # dedup by question number, not content
        lines = r["assessment"].strip().split("\n")
        seen_q, out = set(), []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("Q0") or stripped.startswith("Q1") or stripped.startswith("Q["):
                qkey = stripped[:4]
                if qkey in seen_q:
                    continue
                seen_q.add(qkey)
            out.append(line)
        st.markdown("\n".join(out))

    # Save + download
    os.makedirs("outputs", exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = f"outputs/run_{ts}.md"
    content = f"# AlphaHire Run — {ts}\n\n"
    for k, v in r.items():
        if k != "raw":
            content += f"## {k.upper()}\n{v}\n\n"

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

    # ── Email Simulator ────────────────────────────────────
    st.divider()
    st.markdown('<p class="section-label">Communication</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-title">Interview Invite Simulator</p>', unsafe_allow_html=True)

    # extract top candidate from screening output
    top_candidate = None
    for line in r["screening"].split("\n"):
        if "SHORTLIST" in line.upper():
            for c in candidates:
                if c["name"] in line:
                    top_candidate = c
                    break
        if top_candidate:
            break

    if not top_candidate and candidates:
        top_candidate = candidates[0]

    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.markdown("**Configure**")
        interviewer = st.text_input("Interviewer Name", value="Rajiv Mehta")
        interview_date = st.date_input("Interview Date")
        interview_time = st.selectbox("Time", ["10:00 AM", "11:00 AM", "12:00 PM", "2:00 PM", "3:00 PM"])
        interview_mode = st.selectbox("Mode", ["Video Call (Google Meet)", "In-Person", "Phone"])
        selected_name = st.selectbox(
            "Send to",
            [c["name"] for c in candidates],
            index=0
        )
        selected = next((c for c in candidates if c["name"] == selected_name), top_candidate)

    with col_right:
        st.markdown("**Preview**")
        email_body = f"""Subject: Interview Invitation — Quant Researcher, AI R&D | AlphaHire

Dear {selected["name"]},

Thank you for your interest in the Quant Researcher (AI R&D) role at our office.

After reviewing your profile, we are pleased to invite you for an interview.

Details:
  Date     : {interview_date.strftime("%d %B %Y")}
  Time     : {interview_time}
  Mode     : {interview_mode}
  Role     : Quant Researcher — AI R&D
  Location : New Delhi

Please confirm your availability by replying to this message.

We look forward to speaking with you.

Regards,
{interviewer}
Talent Acquisition, AlphaHire"""

        st.code(email_body, language=None)
        st.download_button(
            label="Download Email",
            data=email_body,
            file_name=f"invite_{selected['name'].replace(' ','_')}.txt",
            mime="text/plain",
            use_container_width=True
        )
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2 = st.columns([3, 1])
    with col1:
        st.success(f"Dossier saved → {out_path}")
    with col2:
        st.download_button(
            label="Download Dossier",
            data=content,
            file_name=f"AlphaHire_{ts}.md",
            mime="text/markdown",
            use_container_width=True
        )