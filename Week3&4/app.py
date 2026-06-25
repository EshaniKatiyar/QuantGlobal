"""
QuantGlobal AI Recruitment System — Streamlit Frontend
Role-based access: TL | HR | Trainee | Candidate
"""

import sys
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import streamlit as st
import bcrypt
import json
import time
from database.db import (
    init_db, get_user, get_all_candidates, get_logs,
    get_quiz_scores, get_avg_stage_duration, create_user,
    get_candidate, get_supervisor_logs,
    get_source_ranking, get_calibration_flags, get_cohort_topic_trends
)
from utils.scheduler_job import start_scheduler
def get_candidate_code_data(candidate_id):
    from database.db import get_conn
    try:
        # This instantly fixes the path AND connects to the correct quantglobal.db!
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT questions, answers FROM candidates WHERE id = ?", (candidate_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row and row["questions"] and row["answers"]:
            return row["questions"], row["answers"]
    except Exception as e:
        print(f"Code fetch error: {e}") # This will print to terminal if it ever fails again
        return None, None
        
    return None, None

st.set_page_config(
    page_title="QuantGlobal | AI Recruitment",
    page_icon="◆",
    layout="wide"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;700&family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"], .stMarkdown, p, span, div, label {
    font-family: 'Inter', -apple-system, sans-serif !important;
}

/* Numbers and scores get the mono treatment, everything else stays Inter */
[data-testid="stMetricValue"], code, .stCode, pre, .qg-tag {
    font-family: 'JetBrains Mono', monospace !important;
}

[data-testid="stMetric"] {
    background: #14161A;
    border: 1px solid #2A2D33;
    border-left: 3px solid #D97A3E;
    border-radius: 4px;
    padding: 16px 18px;
}
[data-testid="stMetricValue"] { font-weight: 700; color: #E8E6E1; }
[data-testid="stMetricLabel"] {
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 0.72rem;
    color: #8A8D93;
}

h1, h2, h3 { font-weight: 600; letter-spacing: -0.01em; }

.stButton > button {
    background: #1A1C20;
    border: 1px solid #2A2D33;
    color: #E8E6E1;
    border-radius: 4px;
    font-weight: 500;
    transition: border-color 0.15s ease;
}
.stButton > button:hover { border-color: #D97A3E; color: #D97A3E; }
.stButton > button[kind="primary"] { background: #D97A3E; border: none; color: #0A0B0D; }
.stButton > button[kind="primary"]:hover { background: #C96A2E; }

[data-testid="stExpander"] { background: #101216; border: 1px solid #2A2D33; border-radius: 4px; }
[data-testid="stSidebar"] { background: #0D0E11; border-right: 1px solid #2A2D33; }

/* Status pills used wherever a stage/decision needs a tag instead of an icon */
.qg-tag {
    display: inline-block;
    font-size: 0.7rem;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    padding: 3px 8px;
    border-radius: 3px;
    border: 1px solid currentColor;
    margin: 2px 0;
}
.qg-tag.pass { color: #7A8471; }
.qg-tag.fail { color: #C24A3E; }
.qg-tag.pending { color: #D97A3E; }

hr { border-color: #2A2D33; }

/* The broad Inter override above also hits Streamlit's own icon glyphs
   (expander arrows, etc.), which rely on a ligature icon font to turn
   text like "keyboard_double_arrow_right" into an actual arrow. Restore
   that font specifically for icon elements so the icon renders instead
   of showing the raw ligature name as overlapping text. */
[data-testid="stIconMaterial"],
span[data-testid="stExpanderIconClosed"],
span[data-testid="stExpanderIconExpanded"],
[class*="material-symbols"] {
    font-family: 'Material Symbols Rounded', 'Material Symbols Outlined', 'Material Icons' !important;
}

</style>
""", unsafe_allow_html=True)

init_db()


def seed_users():
    defaults = [("tl_admin", "TLpass2026!", "TL"), ("hr_admin", "HRpass2026!", "HR")]
    for username, password, role in defaults:
        if not get_user(username):
            pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            create_user(username, pw_hash, role)

seed_users()

# Session state
for key, val in [("logged_in", False), ("username", ""), ("role", ""), ("candidate_id", None)]:
    if key not in st.session_state:
        st.session_state[key] = val


# ── Auth ──────────────────────────────────────────────────────────────────────
def login_page():
    st.markdown("## AutoSource")
    st.markdown("*AI-Native Recruitment & L&D platform*")
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown("### Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login", use_container_width=True):
            user = get_user(username)
            # print(f"DEBUG LOGIN: User fetched -> {user}")
            if user and bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.role = user["role"]
                st.session_state.candidate_id = user.get("candidate_id")
                st.rerun()
            else:
                st.error("Invalid credentials")
        st.markdown("---")
        st.caption("Made for QuantGlobal")



# ── Hiring Velocity ───────────────────────────────────────────────────────────
def compute_hiring_velocity(candidates):
    stages = ["sourced", "screening", "assessment", "scheduled",
              "tl_approved", "offer_sent", "offer_accepted", "onboarded"]
    active = [c for c in candidates if c["status"] == "active"]
    if not active:
        return 0.0
    total = 0
    for c in active:
        idx = stages.index(c["stage"]) if c["stage"] in stages else 0
        remaining = len(stages) - idx
        avg_h = get_avg_stage_duration(c["stage"])
        total += (remaining * avg_h) / 24
    return round(total / len(active), 1)


# ── TL Dashboard ──────────────────────────────────────────────────────────────
def tl_dashboard():
    st.markdown("## TL Dashboard")

    candidates = get_all_candidates()
    velocity = compute_hiring_velocity(candidates)
    active = [c for c in candidates if c["status"] == "active"]
    ppo = [c for c in candidates if c["stage"] == "ppo"]
    pool = [c for c in candidates if c["stage"] == "talent_pool"]
    offboarded = [c for c in candidates if c["stage"] == "offboarded"]

    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Next Hire In", f"{velocity}d" if velocity else "No pipeline")
    col2.metric("Active", len(active))
    col3.metric("PPO", len(ppo))
    col4.metric("Talent Pool", len(pool))

    # Executive summary from Root Supervisor
    sup_logs = get_supervisor_logs()
    tl_summary = next(
        (l["reasoning"] for l in sup_logs if l["supervisor"] == "root_supervisor"
         and "complete" in l["action"]), None
    )
    if tl_summary:
        st.info(f"**Root Supervisor Summary:** {tl_summary}")

    pending_tl = [c for c in candidates if c["stage"] == "scheduled" and c["status"] == "active"]
    overdue_tl = [c for c in pending_tl if c.get("tl_flagged_overdue")]

    tab_approvals, tab_pipeline, tab_outcomes, tab_reasoning = st.tabs([
        f"Approvals ({len(pending_tl)})",
        "Pipeline",
        "Final Outcomes",
        "Reasoning Log"
    ])

    # ── Tab 1: Approvals — the one thing a TL actually needs to act on ───────
    with tab_approvals:
        if overdue_tl:
            st.warning(f"**{len(overdue_tl)} candidate(s) overdue for your decision** "
                       f"(past the {st.session_state.get('tl_timeout', 24)}h window) — "
                       f"the pipeline kept moving for everyone else, but these need your input:")
            for c in overdue_tl:
                st.write(f"• **{c['name']}** ({c['role']}) — pending since {c.get('tl_pending_since', 'unknown')}")
            st.divider()

        if not pending_tl:
            st.info("No candidates currently awaiting your decision.")

        for c in pending_tl:
            alpha_score = c.get('alpha_score_v1', 0)

            with st.expander(f"**{c['name']}** | {c['role']} | Alpha v1: {alpha_score:.1f}/75", expanded=True):
                logs = get_logs(c["id"])

                strengths = next((l["result"] for l in logs if "screening" in l["action"]), "No screening data.")
                st.write(f"**Screening notes:** {strengths}")
                st.write("")

                assessment_log = next((l["result"] for l in logs if "assessment_complete" in l["action"]), "")
                if assessment_log:
                    st.markdown("#### Assessment Breakdown")
                    feedback_parts = assessment_log.split(" | ")
                    for part in feedback_parts:
                        if "Overall:" in part:
                            st.markdown(f"**{part.strip()}**")
                        elif "Strongest:" in part:
                            st.success(f"**{part.strip()}**")
                        elif "Weakest:" in part:
                            st.warning(f"**{part.strip()}**")
                        elif "Feedback:" in part:
                            st.info(f"**{part.strip()}**")

                q_str, a_str = get_candidate_code_data(c["id"])
                if q_str and a_str and q_str != "null":
                    import json
                    try:
                        q_data = json.loads(q_str)
                        a_data = json.loads(a_str)
                        with st.expander("View Code Submission"):
                            st.markdown("**The Practical Challenge:**")
                            st.info(q_data.get("practical", {}).get("question", "No question data found."))
                            st.markdown("**Candidate's Solution:**")
                            st.code(a_data.get("practical_answer", "# No code found."), language="python")
                    except Exception:
                        pass

                st.divider()

                col_a, col_b, _ = st.columns([1, 1, 3])
                with col_a:
                    if st.button("Approve", key=f"ap_{c['id']}", use_container_width=True, type="primary"):
                        from database.db import update_candidate_stage, log_action
                        update_candidate_stage(c["id"], "tl_approved")
                        log_action(c["id"], "tl_approval", "tl_approved_manual", "TL approved via dashboard")
                        st.success("Approved!")
                        st.rerun()
                with col_b:
                    if st.button("Reject", key=f"rj_{c['id']}", use_container_width=True):
                        from database.db import update_candidate_stage, log_action
                        update_candidate_stage(c["id"], "tl_rejected", "rejected")
                        log_action(c["id"], "tl_approval", "tl_rejected_manual", "TL rejected via dashboard")
                        st.error("Rejected.")
                        st.rerun()
                

    # ── Tab 2: Pipeline — every candidate currently in flight ────────────────
    with tab_pipeline:
        if not candidates:
            st.info("No candidates yet. Ask HR to trigger the pipeline.")
        else:
            status_tag = {"ppo": ("PPO", "pass"), "talent_pool": ("TALENT POOL", "pending"),
                           "offboarded": ("OFFBOARDED", "fail"), "active": ("ACTIVE", "pass"),
                           "rejected": ("REJECTED", "fail")}
            for c in candidates:
                label, cls = status_tag.get(c["status"], (c["status"].upper(), "pending"))
                with st.expander(f"**{c['name']}** | {c['role']} | `{c['stage']}`"):
                    st.markdown(f'<span class="qg-tag {cls}">{label}</span>', unsafe_allow_html=True)
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Alpha v1", f"{c['alpha_score_v1']:.1f}/75")
                    col2.metric("Alpha v2", f"{c['alpha_score_v2']:.1f}/100" if c['alpha_score_v2'] else "—")
                    col3.metric("Status", c["status"].upper())

                    quiz_scores = get_quiz_scores(c["id"])
                    if quiz_scores:
                        st.markdown("**L&D Progress:**")
                        weeks = sorted(set(q["week"] for q in quiz_scores))
                        for w in weeks:
                            w_scores = [q["score"] for q in quiz_scores if q["week"] == w]
                            avg = sum(w_scores) / len(w_scores)
                            tag_cls = "pass" if avg >= 70 else "pending" if avg >= 50 else "fail"
                            st.markdown(
                                f'Week {w}: <span class="qg-tag {tag_cls}">{avg:.1f}%</span>',
                                unsafe_allow_html=True
                            )

                    if c["stage"] == "ppo":
                        decision_log = next(
                            (l["result"] for l in get_logs(c["id"]) if "ppo_awarded" in l["action"]), ""
                        )
                        if decision_log:
                            st.success(f"**Decision reasoning:** {decision_log[:200]}")

    # ── Tab 3: Final Outcomes ─────────────────────────────────────────────────
    with tab_outcomes:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.success(f"PPO: {len(ppo)}")
            for c in ppo:
                st.write(f"• {c['name']} — {c['alpha_score_v2']:.1f}/100")
        with col2:
            st.info(f"Talent Pool: {len(pool)}")
            for c in pool:
                st.write(f"• {c['name']} — {c['alpha_score_v2']:.1f}/100")
        with col3:
            st.error(f"Offboarded: {len(offboarded)}")
            for c in offboarded:
                st.write(f"• {c['name']}")

    # ── Tab 4: Reasoning Log ──────────────────────────────────────────────────
    with tab_reasoning:
        if sup_logs:
            for log in sup_logs[:20]:
                role_tag = {"root_supervisor": "ROOT", "recruitment_supervisor": "RECRUITMENT",
                            "ld_supervisor": "L&D"}.get(log["supervisor"], log["supervisor"].upper())
                st.caption(f"`{log['timestamp']}` **[{role_tag}]** "
                           f"`{log['action']}`: {log['reasoning'][:150]}")
        else:
            st.info("No supervisor decisions logged yet.")


# ── HR Dashboard ──────────────────────────────────────────────────────────────
# ── HR Dashboard ──────────────────────────────────────────────────────────────
def hr_dashboard():
    st.markdown("## HR Dashboard")

    from database.db import get_all_candidates, get_quiz_scores, get_logs
    
    # Fetch global data needed across tabs
    candidates = get_all_candidates()
    
    # Create the beautiful tabbed UI
    tab1, tab2, tab3, tab4 = st.tabs([
        "Pipeline & Metrics", 
        "Recruitment Hub", 
        "L&D Operations", 
        "System Logs"
    ])
    

    from database.db import get_all_candidates, get_quiz_scores, get_logs
    
    # --- THE ONCE-AND-FOR-ALL FIX: Read Alpha scores directly from Agent Logs ---
    def get_real_alpha_v1(candidate):
        # 1. Check if it's already saved in the main table
        if candidate.get("alpha_v1"):
            return candidate["alpha_v1"]
            
        # 2. If not, sweep the agent logs!
        logs = get_logs(candidate["id"])
        
        # Check Assessment Agent first (it has the final, most accurate Phase 1 score)
        for l in logs:
            if l["action"] == "assessment_complete" and "Alpha v1 final:" in l["result"]:
                try:
                    return l["result"].split("Alpha v1 final: ")[1].split("/")[0].strip()
                except:
                    pass
                    
        # Check Screener Agent if Assessment hasn't run yet
        for l in logs:
            if l["action"] == "alpha_score_v1_computed" and "Alpha v1:" in l["result"]:
                try:
                    return l["result"].split("Alpha v1: ")[1].split(" |")[0].strip()
                except:
                    pass
                    
        return "N/A"
    # --- Fetch raw code directly from DB safely ---
    
    # ----------------------------------------------
    # -------------------------------------------------------------------------
    # ==========================================
    # TAB 1: PIPELINE CONTROL & DYNAMIC METRICS
    # ==========================================
    with tab1:
        st.markdown("### Pipeline Control")
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("Trigger Pipeline", use_container_width=True):
                import subprocess
                import sys
                
                # 1. Show a loading state so you don't have to guess when it's done
                with st.spinner("AI Pipeline is running... This takes about 60 seconds. Please wait."):
                    
                    # 2. Run the engine and capture all the terminal text
                    result = subprocess.run([sys.executable, "main.py"], capture_output=True, text=True, encoding="utf-8")
                    
                    # 3. Create the missing file and save the text into it!
                    with open("pipeline.log", "w", encoding="utf-8") as log_file:
                        log_file.write(result.stdout)
                        if result.stderr:
                            log_file.write("\n[ERRORS]\n" + result.stderr)
                            
                st.success("Pipeline complete! Reloading data...")
                
                # 4. Magically auto-refresh the page to show the new candidates!
                st.rerun()
        with col2:
            st.info("Auto-runs every Monday 9:00 AM | Manual trigger available above")

        st.markdown("---")
        st.markdown("### Feedback & Continuous Improvement Loops")
        
        # --- DYNAMIC METRIC CALCULATIONS ---
        
        # 1. Sourcing Yield (How many made it through Recruitment?)
        total_sourced = len(candidates)
        # Count anyone who made it past the initial assessments
        passed_recruitment = len([c for c in candidates if "week" in c["stage"] or c["stage"] in ["onboarded", "offer_accepted", "offer_sent", "ppo", "talent_pool", "offboarded"]])
        yield_pct = (passed_recruitment / total_sourced * 100) if total_sourced > 0 else 0

        # 2. Score Calibration (Base Alpha vs Final Alpha)
        completed_ld = [c for c in candidates if c.get("alpha_v2") is not None]
        avg_v1 = sum(c.get("alpha_v1", 0) for c in completed_ld) / len(completed_ld) if completed_ld else 0
        avg_v2 = sum(c.get("alpha_v2", 0) for c in completed_ld) / len(completed_ld) if completed_ld else 0

        # 3. L&D Cohort Health (Average Quiz Scores by Week)
        all_quizzes = []
        for c in candidates:
            c_quizzes = get_quiz_scores(c["id"])
            if c_quizzes:
                all_quizzes.extend(c_quizzes)
                
        week_avgs = {}
        for q in all_quizzes:
            w = q["week"]
            week_avgs.setdefault(w, []).append(q["score"])

        # --- RENDER DYNAMIC UI ---
        metrics_col1, metrics_col2, metrics_col3 = st.columns(3)
        
        with metrics_col1:
            st.markdown("**Loop 1 — Sourcing Yield**")
            if total_sourced > 0:
                st.markdown(f"`Overall` : {passed_recruitment}/{total_sourced} passed ({yield_pct:.0f}%)")
            else:
                st.markdown("`No data yet`")
            st.caption("Yield rate from Sourcing to L&D Onboarding.")
            
        with metrics_col2:
            st.markdown("**Loop 2 — Score Calibration**")
            if completed_ld:
                st.markdown(f"**Avg Base Alpha v1:** {avg_v1:.1f}/75")
                st.markdown(f"**Avg Final Alpha v2:** {avg_v2:.1f}/100")
                delta = avg_v2 - avg_v1
                st.caption(f"Average L&D velocity boost: +{delta:.1f} points")
            else:
                st.markdown("`Awaiting first final evaluations.`")
            
        with metrics_col3:
            st.markdown("**Loop 3 — Cohort Quiz Health**")
            if week_avgs:
                for w in sorted(week_avgs.keys()):
                    scores = week_avgs[w]
                    avg_score = sum(scores) / len(scores)
                    tag_cls = "pass" if avg_score >= 70 else "pending" if avg_score >= 60 else "fail"
                    st.markdown(
                        f'<span class="qg-tag {tag_cls}">{avg_score:.1f}%</span> **Week {w}** (n={len(scores)})',
                        unsafe_allow_html=True
                    )
            else:
                st.markdown("`No quiz data recorded yet.`")
            st.caption("Aggregated performance across all trainees.")
        render_quiz_heatmap()
        render_candidate_timeline()

    # ==========================================
    # TAB 2: RECRUITMENT HUB (Sourcing to Offer)
    # ==========================================
    with tab2:
        st.markdown("### Recruitment Candidates")
        
        stages = ["All"] + sorted(list(set(c["stage"] for c in candidates if "week" not in c["stage"] and c["stage"] != "onboarded")))
        selected_stage = st.selectbox("Filter by Stage", stages, key="recruitment_filter")

        recruitment_candidates = [c for c in candidates if "week" not in c["stage"] and c["stage"] not in ["onboarded", "talent_pool", "offboarded", "ppo"]]

        if not recruitment_candidates:
            st.info("No active candidates in the recruitment phase.")
        else:
            for c in recruitment_candidates:
                if selected_stage != "All" and c["stage"] != selected_stage:
                    continue
                
                with st.expander(f"{c['name']} | Role: {c['role']} | Stage: {c['stage'].upper()}"):
                    
                    real_alpha = get_real_alpha_v1(c)
                    logs = get_logs(c["id"])
                    
                    # 1. CLEAN METRICS ROW
                    m1, m2, m3 = st.columns(3)
                    m1.markdown(f"**Email:** {c['email']}")
                    m2.markdown(f"**Alpha v1:** {real_alpha}")
                    m3.markdown(f"**Stage:** `{c['stage'].upper()}`")
                    
                    st.divider()

                    # 2. EXTRACT INTERVIEW SCHEDULE
                    interview_log = next((l for l in logs if l["action"] == "interview_scheduled"), None)
                    if interview_log:
                        clean_schedule = interview_log['result'].replace(' | ', '  •  ')
                        st.success(f"**INTERVIEW SCHEDULED:**\n\n{clean_schedule}")
                    
                    # 3. EXTRACT ASSESSMENT FEEDBACK
                    assessment_log = next((l for l in logs if l["action"] == "assessment_complete"), None)
                    if assessment_log:
                        st.markdown("#### Assessment Breakdown")
                        feedback_parts = assessment_log["result"].split(" | ")
                        for part in feedback_parts:
                            if "Overall:" in part:
                                st.markdown(f"**{part.strip()}**")
                            elif "Strongest:" in part:
                                st.markdown(f"**{part.strip()}**")
                            elif "Weakest:" in part:
                                st.markdown(f"**{part.strip()}**")
                            elif "Feedback:" in part:
                                st.info(f"**{part.strip()}**")
                    elif c['stage'].lower() == 'screening':
                        # Make the screening stage look intentional, not empty!
                        st.info("**Status:** Candidate is currently passing through the screening phase. Awaiting Sandbox Assessment.")

                    # 4. VIEW CODE SUBMISSION (Using our safe DB fetcher!)
                    q_str, a_str = get_candidate_code_data(c["id"])
                    if q_str and a_str and q_str != "null":
                        import json
                        try:
                            q_data = json.loads(q_str)
                            a_data = json.loads(a_str)
                            
                            with st.expander("View Code Submission"):
                                st.markdown("**The Practical Challenge:**")
                                st.info(q_data.get("practical", {}).get("question", "No question data found."))
                                
                                st.markdown("**Candidate's Solution:**")
                                st.code(a_data.get("practical_answer", "# No code found."), language="python")
                        except Exception:
                            pass
                                
                    # 5. HIDE RAW LOGS
                    if logs:
                        st.write("") # Spacer
                        with st.expander("View Raw Agent Logs"):
                            for l in logs:
                                st.caption(f"[{l['timestamp']}] **{l['action']}** - {l['result']}")
#TAB 3: L&D OPERATIONS
    with tab3:
        st.markdown("### L&D Operations Dashboard")
        
        ld_candidates = [c for c in candidates if "week" in c["stage"] or c["stage"] in ["onboarded", "ppo", "talent_pool", "offboarded", "awaiting_decision"]]

        if not ld_candidates:
            st.info("No candidates in the L&D phase.")
        else:
            for c in ld_candidates:
                # 1. Calculate Growth Delta for the header
                alpha_v1 = float(get_real_alpha_v1(c))
                alpha_v2 = float(c.get('alpha_score_v2') or alpha_v1) 
                growth = alpha_v2 - alpha_v1
                
                with st.expander(f"{c['name']} | {c['role']} | {c['stage'].upper()}", expanded=True):
                    
                    # Header Metrics
                    col_m1, col_m2, col_m3 = st.columns(3)
                    col_m1.metric("Base Alpha (v1)", f"{alpha_v1:.1f}")
                    col_m2.metric("Final Alpha (v2)", f"{alpha_v2:.1f}", delta=f"{growth:+.1f}")
                    col_m3.metric("Status", c['stage'].replace('_', ' ').title())

                    with st.popover("Reset Trainee Password"):
                        st.caption(f"Generates a new login password for {c['name']}'s Trainee account.")
                        if st.button("Confirm Reset", key=f"reset_pw_{c['id']}"):
                            from database.db import reset_trainee_password
                            import random
                            import string
                            import hashlib

        # 1. Generate a random 8-character plaintext password
                            new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        
        # 2. Hash the password for the database
                            new_password_hash = hashlib.sha256(new_password.encode()).hexdigest()

        # 3. Pass BOTH the candidate ID and the new hashed password to db.py
                            reset_trainee_password(c["id"], new_password_hash)

                            st.success(f"New password for **{c['name']}**:")
                            st.code(new_password, language=None)
                            st.caption("Share this with the trainee directly — it won't be shown again after you close this.")

                    st.divider()

                    # 2. Dynamic Tabbed UI
                    quiz_scores = get_quiz_scores(c["id"])
                    logs = get_logs(c["id"])
                    coach_logs = [l for l in logs if "module_delivered" in l["action"]]
                    
                    # Create tabs for the 4 weeks
                    tab_list = st.tabs(["Week 1", "Week 2", "Week 3", "Week 4"])
                    
                    for i, tab in enumerate(tab_list, 1):
                        with tab:
                            # Filter quiz data for this week
                            w_scores = [q["score"] for q in quiz_scores if q["week"] == i]
                            avg = sum(w_scores) / len(w_scores) if w_scores else None
                            
                            col_a, col_b = st.columns([1, 2])
                            
                            with col_a:
                                st.markdown("#### Assessment")
                                if avg is not None:
                                    st.metric(f"Week {i} Avg", f"{avg:.1f}%")
                                else:
                                    st.write("No data")
                                    
                            with col_b:
                                st.markdown("#### Coaching")
                                # Fix the "Week X: Week X:" bug using a simple replace
                                # Look for the week number inside the actual text or the stage!
                                module = next((cl['result'] for cl in coach_logs if f"Week {i}" in cl.get('result', '') or str(i) in cl.get('stage', '')), "Pending...")
                                clean_module = module.replace(f"Week {i}: Week {i}:", f"Week {i}:").replace('Title: ', '')
                                st.success(clean_module)
    # ==========================================
    # TAB 4: SYSTEM LOGS
    # ==========================================
    with tab4:
        st.markdown("### Supervisor Decision Log")
        
        try:
            with open("pipeline.log", "r", encoding="utf-8") as f:
                logs = f.readlines()
                
            if not logs:
                st.info("Log file is empty.")
            else:
                for line in reversed(logs[-50:]):
                    st.text(line.strip())
        except FileNotFoundError:
            st.warning("No pipeline.log file found yet. Run the pipeline to generate logs.")

        


def trainee_dashboard():
    st.markdown("## Trainee Portal")
    candidate_id = st.session_state.candidate_id
    if not candidate_id:
        st.error("No profile linked.")
        return

    candidate = get_candidate(candidate_id)
    if not candidate:
        st.error("Profile not found.")
        return

    # --- TOP METRICS HEADER ---
    st.markdown(f"### Welcome, {candidate['name']}")
    col1, col2, col3 = st.columns(3)
    col1.metric("Role", candidate["role"])
    
    alpha_v2 = candidate.get('alpha_score_v2')
    col2.metric("Alpha v2", f"{alpha_v2:.1f}/100" if alpha_v2 else "In Progress")
    col3.metric("Status", candidate["stage"].replace('_', ' ').upper())

    st.markdown("---")
    
    # --- THE LMS CURRICULUM TABS ---
    st.markdown("### Your L&D Curriculum")
    
    quiz_scores = get_quiz_scores(candidate_id)
    logs = get_logs(candidate_id)
    
    tabs = st.tabs(["Week 1", "Week 2", "Week 3", "Week 4"])
    
    for i, tab in enumerate(tabs, 1):
        with tab:
            # Dynamically locate the coach log for this specific week
            coach_log = next((l for l in logs if "module_delivered" in l["action"] and str(i) in l.get('stage', '')), None)
            
            if coach_log:
                st.markdown(f"#### Week {i} Reading & Focus Areas")
                # Fix the double-week naming bug automatically
                clean_module = coach_log['result'].replace(f"Week {i}: Week {i}:", f"Week {i}:").replace('Title: ', '')
                st.info(clean_module)
                
                st.markdown("#### Weekly Assessment")
                w_scores = [q for q in quiz_scores if q["week"] == i]

                if w_scores:
                    # Dedupe by topic, keeping the most recent score for each
                    # (a re-run of this week's quiz writes new rows rather than
                    # overwriting old ones, so without this the same topic can
                    # show up more than once).
                    latest_by_topic = {}
                    for q in w_scores:
                        existing = latest_by_topic.get(q["topic"])
                        if existing is None or q.get("id", 0) >= existing.get("id", 0):
                            latest_by_topic[q["topic"]] = q
                    deduped_scores = list(latest_by_topic.values())

                    avg = sum(q["score"] for q in deduped_scores) / len(deduped_scores)
                    st.success(f"**Assessment Completed!** Score: {avg:.1f}%")

                    for q in deduped_scores:
                        st.write(f"  • {q['topic']}: {q['score']:.1f}%")
                else:
                    st.write("Review the material above before starting your assessment.")
                    if st.button(f"Start Week {i} Assessment", key=f"quiz_{candidate_id}_{i}", type="primary"):
                        st.warning("Loading Assessment Environment... (Interactive player launches here)")
            else:
                st.write(f"*Week {i} module is locked or still generating.*")

    # --- FINAL DECISION OUTCOMES (Your exact original logic) ---
    if candidate["stage"] in ["ppo", "talent_pool", "offboarded"]:
        st.markdown("---")
        if candidate["stage"] == "ppo":
            st.success(f"**Pre-Placement Offer (PPO)** — Alpha Score: {alpha_v2:.1f}/100")
            decision_log = next((l["result"] for l in logs if "ppo_awarded" in l["action"]), "")
            if decision_log:
                st.write(f"**Feedback:** {decision_log}")
                
        elif candidate["stage"] == "talent_pool":
            st.info(f"**Talent Pool** — You'll be re-engaged in 6 months. Alpha Score: {alpha_v2:.1f}/100")
            
        else:
            st.error("Programme concluded. Thank you for participating.")
            decision_log = next((l["result"] for l in logs if "offboard" in l["action"]), "")
            if decision_log:
                st.write(f"**Feedback:** {decision_log}")


# ── Candidate Portal ──────────────────────────────────────────────────────────
def candidate_portal():
    st.markdown("## Candidate Portal")
    candidate_id = st.session_state.candidate_id
    if not candidate_id:
        st.error("No profile linked.")
        return

    candidate = get_candidate(candidate_id)
    if not candidate:
        st.error("Profile not found.")
        return

    st.markdown(f"### Hello, {candidate['name']}")
    st.markdown(f"**Role:** {candidate['role']} | **Stage:** `{candidate['stage']}`")

    if candidate["stage"] == "offer_sent":
        st.markdown("---")
        st.markdown("### Your Offer Letter")
        logs = get_logs(candidate_id)
        offer_log = next((l for l in logs if l["action"] == "offer_generated"), None)
        
        if offer_log:
            # Format the text with HTML line breaks
            offer_content = offer_log["result"].replace('\n', '<br>')
            
            # THE FIX: Keep this completely flush left! Do not indent the HTML!
            st.markdown(f"""
<div style="background-color: #ffffff; color: #000000; padding: 60px 50px; margin: 20px auto; max-width: 800px; border: 1px solid #cccccc; border-radius: 4px; box-shadow: 0 10px 20px rgba(0,0,0,0.15); font-family: 'Georgia', 'Times New Roman', serif; line-height: 1.6; font-size: 16px; max-height: 600px; overflow-y: auto;">
    <div style="text-align: right; color: #555; margin-bottom: 30px; border-bottom: 2px solid #2c3e50; padding-bottom: 10px;">
        <h2 style="margin: 0; color: #2c3e50; font-family: 'Arial', sans-serif;">QuantGlobal</h2>
        <small>Delhi-NCR, India</small>
    </div>
    <p>{offer_content}</p>
    <div style="margin-top: 50px;">
        <p>Sincerely,</p><br>
        <p><strong>Head of Talent</strong><br>QuantGlobal</p>
    </div>
</div>
""", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### Required Onboarding Documents")
        st.info("As per compliance, please upload a merged PDF of your Aadhaar/PAN and Degree Certificate. These will be AES-256 encrypted upon acceptance.")
        
        # 1. The File Uploader
        uploaded_file = st.file_uploader("Upload Documents (PDF)", type=["pdf"])
        
        # 2. The SINGLE Consent Box
        consent = st.checkbox(
            "I consent to QuantGlobal processing my personal data and encrypting my uploaded documents for compliance."
        )
        
        # 3. The SINGLE set of Buttons
        col1, col2 = st.columns(2)
        if col1.button("Accept Offer & Submit Docs", type="primary"):
            if not consent or uploaded_file is None:
                st.error("Please upload your document and check the consent box before accepting.")
            else:
                from database.db import update_candidate_stage, log_action, set_consent
                from utils.encryption import encrypt
                from agents.onboarding import run_onboarding

                set_consent(candidate_id)
                update_candidate_stage(candidate_id, "offer_accepted")

                # Actually encrypt the uploaded document now, not just log its filename
                doc_bytes = uploaded_file.read()
                try:
                    encrypted_doc = encrypt(doc_bytes.decode("latin-1"))
                    encryption_note = f"Document '{uploaded_file.name}' encrypted (AES-256)"
                except Exception as e:
                    encryption_note = f"Document '{uploaded_file.name}' received — encryption failed: {e}"

                log_action(candidate_id, "offer", "offer_accepted_portal",
                           f"Offer accepted | {encryption_note}")

                # THE FIX: don't wait for the next pipeline run to onboard this
                # candidate — create their Trainee login right now so the
                # portal is usable immediately after acceptance.
                candidate_row = get_candidate(candidate_id)
                onboarding_state = run_onboarding({"accepted_candidates": [candidate_row]})
                onboarded = onboarding_state.get("onboarded_candidates", [])

                week1_score = None
                week1_offboarded = False

                if onboarded:
                    from agents.coach import run_coach
                    from agents.quiz import run_quiz

                    # onboarding returns "id", but coach/quiz agents expect "candidate_id"
                    trainee = {**onboarded[0], "candidate_id": onboarded[0]["id"]}

                    coach_state = run_coach({
                        "current_trainees": [trainee],
                        "current_week": 1,
                        "ld_coaching_focus": ""
                    })
                    coached = coach_state.get("coached_candidates", [])

                    quiz_state = run_quiz({
                        "coached_candidates": coached,
                        "current_week": 1
                    })

                    quiz_results = quiz_state.get("quiz_results", [])
                    early_offboarded = quiz_state.get("early_offboarded", [])

                    if quiz_results:
                        week1_score = quiz_results[0].get("last_quiz", {}).get("overall_score")
                    elif early_offboarded:
                        week1_offboarded = True

                    st.session_state["just_onboarded_creds"] = {
                        "username": onboarded[0]["trainee_username"],
                        "password": onboarded[0]["trainee_password"],
                        "week1_score": week1_score,
                        "week1_offboarded": week1_offboarded
                    }
                else:
                    st.session_state["just_onboarded_creds"] = None

                st.rerun()
            
        if col2.button("Decline"):
            from database.db import update_candidate_stage, log_action
            update_candidate_stage(candidate_id, "offer_declined", "rejected")
            log_action(candidate_id, "offer", "offer_declined_portal", "Candidate declined")
            st.warning("Offer declined.")
            st.rerun()

    else:
        # Once accepted, show their Trainee credentials (if just onboarded)
        # instead of just a bare stage label with no next action.
        creds = st.session_state.get("just_onboarded_creds")
        if creds:
            st.success("Offer accepted and documents secured!")
            st.markdown("### Your Trainee Portal Credentials")
            st.info(
                f"**Username:** `{creds['username']}`  \n"
                f"**Password:** `{creds['password']}`"
            )
            if creds.get("week1_offboarded"):
                st.warning(
                    "Your Week 1 assessment has already been generated and scored below "
                    "the L&D checkpoint threshold. Log in as a Trainee to view your feedback."
                )
            elif creds.get("week1_score") is not None:
                st.markdown(
                    f"**Week 1 is ready** — coaching module delivered and quiz scored "
                    f"(**{creds['week1_score']:.1f}%**). Log out and log back in as a "
                    f"**Trainee** to view it now."
                )
            else:
                st.markdown(
                    "Log out and log back in as a **Trainee** — your Week 1 content "
                    "will appear shortly."
                )
            st.session_state["just_onboarded_creds"] = None  # show once, then clear
        else:
            st.info(f"Application at stage: **{candidate['stage']}**")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    start_scheduler()

    if not st.session_state.logged_in:
        login_page()
        return

    with st.sidebar:
        st.markdown(f"**{st.session_state.username}**")
        st.caption(f"Role: {st.session_state.role}")
        st.markdown("---")
        if st.button("Logout"):
            for key in ["logged_in", "username", "role", "candidate_id"]:
                st.session_state[key] = False if key == "logged_in" else ""
            st.rerun()

    role = st.session_state.role
    if role == "TL":
        tl_dashboard()
    elif role == "HR":
        hr_dashboard()
    elif role == "Trainee":
        trainee_dashboard()
    elif role == "Candidate":
        candidate_portal()
    else:
        st.error("Unknown role.")

def render_quiz_heatmap():
    """Trainee × topic quiz score heatmap across all weeks."""
    from database.db import get_quiz_heatmap_data
    data = get_quiz_heatmap_data()
    if not data:
        return
    st.markdown("---")
    st.markdown("### Quiz Performance Heatmap")
    st.caption("Trainees × topics, averaged across all weeks. Red = weak, green = strong.")
    try:
        import pandas as pd
        import plotly.express as px
        df = pd.DataFrame(data)
        pivot = df.pivot_table(index="name", columns="topic", values="score", aggfunc="mean")
        fig = px.imshow(
            pivot, text_auto=".0f", aspect="auto",
            color_continuous_scale="RdYlGn", zmin=0, zmax=100,
            labels=dict(x="Topic", y="Trainee", color="Score %")
        )
        fig.update_layout(height=max(300, 60 * len(pivot)), margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.warning(f"Heatmap unavailable: {e}")


def render_candidate_timeline():
    """Gantt-style timeline: time each candidate spent at each stage."""
    from database.db import get_stage_timeline
    data = get_stage_timeline()
    if not data:
        return
    st.markdown("---")
    st.markdown("### Candidate Lifecycle Timeline")
    st.caption("Each bar = time a candidate spent at a stage (drives the Hiring Velocity metric).")
    try:
        import pandas as pd
        import plotly.express as px
        df = pd.DataFrame(data)
        df["entered_at"] = pd.to_datetime(df["entered_at"], errors="coerce")
        df = df.dropna(subset=["entered_at"]).sort_values(["candidate_id", "entered_at"])
        
        # FIX: Force duration_hours to be numeric and replace NaN with 1 to prevent the crash
        df["duration_hours"] = pd.to_numeric(df["duration_hours"], errors="coerce").fillna(1)
        
        rows = []
        for cid, grp in df.groupby("candidate_id"):
            grp = grp.reset_index(drop=True)
            for i in range(len(grp)):
                start = grp.loc[i, "entered_at"]
                if i + 1 < len(grp):
                    end = grp.loc[i + 1, "entered_at"]
                else:
                    dur = grp.loc[i, "duration_hours"]
                    end = start + pd.Timedelta(hours=max(dur, 0.5))
                rows.append(dict(Candidate=grp.loc[i, "name"], Stage=grp.loc[i, "stage"],
                                 Start=start, Finish=end))
        if not rows:
            return
        tdf = pd.DataFrame(rows)
        fig = px.timeline(tdf, x_start="Start", x_end="Finish", y="Candidate",
                          color="Stage", labels={"Candidate": ""})
        fig.update_yaxes(autorange="reversed")
        fig.update_layout(height=max(300, 50 * tdf["Candidate"].nunique()),
                          margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.warning(f"Timeline unavailable: {e}")

if __name__ == "__main__":
    main()