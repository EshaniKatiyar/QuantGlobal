"""
QuantPulse — QuantGlobal Autonomous Marketing
Auth: Admin (run pipeline) | Viewer (read-only)
"""

import streamlit as st
import json, os, datetime
from pathlib import Path
from dotenv import load_dotenv

if "sidebar_state" not in st.session_state:
    st.session_state.sidebar_state = "expanded"

load_dotenv()

OUTPUT_DIR  = Path("data/outputs")
REPORTS_DIR = Path("data/reports")
MEMORY_FILE = Path("data/content_memory.json")
SERIES_FILE = Path("data/series_state.json")

for d in [OUTPUT_DIR, REPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── QuantGlobal Brand CSS ─────────────────────────────────────────────────────
BRAND_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

.stApp {
    background: #0A0B0E;
    font-family: 'Inter', sans-serif;
    color: #B0B4C0;
}

[data-testid="collapsedControl"] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    z-index: 999999 !important;
}

/* ── Hide chrome ── */
.stDeployButton, #MainMenu, footer, header,
div[data-testid="stToolbar"] { display: none !important; }

/* ── Sidebar ── */
div[data-testid="stSidebarContent"] {
    background: #07080B;
    border-right: 1px solid #13141A;
    padding-top: 0;
}
div[data-testid="stSidebarContent"] div[role="radiogroup"] label {
    font-size: 0.88rem !important;
    color: #E2E4EC !important;
    letter-spacing: 0.01em !important;
    padding: 0.35rem 0 !important;
    font-weight: 400 !important;
    transition: color 0.15s !important;
}
div[data-testid="stSidebarContent"] div[role="radiogroup"] label:has(input:checked) {
    color: #E2E4EC !important;
    font-weight: 500 !important;
}
div[data-testid="stSidebarContent"] div[role="radiogroup"] [data-testid="stMarkdownContainer"] p {
    font-size: 0.88rem !important;
}
div[data-testid="stSidebarContent"] div[role="radiogroup"] [data-testid="stWidgetLabel"] { display: none; }

/* ── Login — full viewport split ── */
.login-root {
    position: fixed;
    inset: 0;
    display: flex;
    background: #0A0B0E;
}
.login-left {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding: 3rem 4rem;
    border-right: 1px solid #13141A;
}
.login-left-brand {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: #BFA050;
}
.login-left-brand span { color: #3A2E14; }
.login-left-headline {
    font-size: 2.8rem;
    font-weight: 300;
    color: #EDEEF2;
    line-height: 1.15;
    letter-spacing: -0.03em;
    max-width: 420px;
}
.login-left-headline strong {
    font-weight: 600;
    color: #BFA050;
}
.login-left-footer {
    font-size: 0.72rem;
    color: #E2E4EC;
    letter-spacing: 0.05em;
}
.login-right {
    width: 440px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 3rem 3.5rem;
}
.login-right-title {
    font-size: 1.5rem;
    font-weight: 500;
    color: #EDEEF2;
    letter-spacing: -0.02em;
    margin-bottom: 0.4rem;
}
.login-right-sub {
    font-size: 0.75rem;
    color: #E2E4EC;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    padding-bottom: 2rem;
    border-bottom: 1px solid #13141A;
    margin-bottom: 2rem;
}

/* ── Inputs ── */
div[data-testid="stTextInput"] label {
    font-size: 0.7rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
    color: #E2E4EC !important;
    margin-bottom: 0.35rem !important;
}
div[data-testid="stTextInput"] input {
    background: #0D0E13 !important;
    border: 1px solid #1A1C26 !important;
    border-radius: 4px !important;
    color: #D8DAE4 !important;
    font-size: 1rem !important;
    padding: 0.75rem 1rem !important;
    transition: border-color 0.2s !important;
}
div[data-testid="stTextInput"] input:focus {
    border-color: #BFA050 !important;
    box-shadow: 0 0 0 2px rgba(191,160,80,0.08) !important;
    outline: none !important;
}

/* ── Buttons ── */
.stButton > button {
    background: #BFA050 !important;
    border: none !important;
    color: #07080B !important;
    border-radius: 4px !important;
    font-size: 0.78rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
    padding: 0.75rem 1rem !important;
    transition: all 0.18s ease !important;
    width: 100% !important;
}
.stButton > button:hover {
    background: #D4AF5A !important;
}
/* Sidebar/secondary buttons — ghost style */
div[data-testid="stSidebarContent"] .stButton > button {
    background: transparent !important;
    border: 1px solid #1A1C26 !important;
    color: #E2E4EC !important;
}
div[data-testid="stSidebarContent"] .stButton > button:hover {
    border-color: #BFA050 !important;
    color: #BFA050 !important;
}

/* ── Page headers ── */
.qp-header {
    padding-bottom: 1.1rem;
    margin-bottom: 2rem;
    border-bottom: 1px solid #13141A;
}
.qp-header h1 {
    font-size: 1.4rem;
    font-weight: 500;
    color: #EDEEF2;
    letter-spacing: -0.02em;
}

/* ── Cards ── */
.metric-box, .score-card, .roi-card, .agent-card {
    background: #0D0E13;
    border: 1px solid #13141A;
    border-radius: 6px;
    padding: 1.4rem 1.5rem;
    transition: border-color 0.2s;
}
.metric-box:hover, .score-card:hover, .roi-card:hover {
    border-color: rgba(191,160,80,0.25);
}
.metric-label, .score-card .label, .roi-card .label {
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #E2E4EC;
    margin-bottom: 0.6rem;
}
.metric-value, .score-card .value, .roi-card .value {
    font-size: 1.9rem;
    font-weight: 300;
    color: #EDEEF2;
    letter-spacing: -0.03em;
    line-height: 1;
    margin-bottom: 0.5rem;
}
.metric-sub, .score-card .sub, .roi-card .sub {
    font-size: 0.76rem;
    color: #E2E4EC;
}

/* ── Status colours ── */
.text-gold  { color: #BFA050 !important; }
.text-green { color: #3ECF8E !important; }
.text-amber { color: #F59E0B !important; }
.text-red   { color: #F87171 !important; }

.status-badge {
    display: inline-block;
    padding: 0.15rem 0.6rem;
    border-radius: 2px;
    font-size: 0.62rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}
.badge-clear { border: 1px solid #3ECF8E; color: #3ECF8E; }
.badge-warn  { border: 1px solid #F59E0B; color: #F59E0B; }
.badge-fail  { border: 1px solid #F87171; color: #F87171; }

/* ── Tables ── */
table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
th {
    text-align: left;
    padding: 0.7rem 0.75rem;
    border-bottom: 1px solid #13141A;
    color: #E2E4EC;
    font-size: 0.68rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.09em;
}
td {
    padding: 0.8rem 0.75rem;
    border-bottom: 1px solid #0D0E13;
    color: #8A8E9E;
    font-size: 0.9rem;
}

/* ── Misc ── */
hr { border: none; border-top: 1px solid #13141A !important; margin: 1.5rem 0 !important; }
::-webkit-scrollbar { width: 3px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #1A1C26; }
::-webkit-scrollbar-thumb:hover { background: #BFA050; }
</style>
"""

# ── Auth ──────────────────────────────────────────────────────────────────────
CREDENTIALS = {
    "admin":  os.getenv("ADMIN_PASSWORD",  "quantglobal_admin_2025"),
    "viewer": os.getenv("VIEWER_PASSWORD", "quantglobal_viewer_2025"),
}

def check_auth(username, password):
    expected = CREDENTIALS.get(username.lower())
    return expected and password == expected

def login_screen():
    st.markdown(BRAND_CSS, unsafe_allow_html=True)

    left, right = st.columns([1.1, 0.75])

    with left:
        st.markdown("""
        <div style="padding:3rem 2rem 3rem 1rem;min-height:92vh;display:flex;flex-direction:column;justify-content:space-between;border-right:1px solid #13141A;">
            <div style="font-size:0.72rem;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;color:#BFA050;">
                QUANT<span style="color:#3A2E14;">PULSE</span>
            </div>
            <div>
                <div style="font-size:3rem;font-weight:300;color:#EDEEF2;line-height:1.15;letter-spacing:-0.03em;max-width:480px;margin-bottom:1.5rem;">
                    Autonomous<br><strong style="font-weight:600;color:#BFA050;">marketing</strong><br>for QuantGlobal.
                </div>
                <div style="font-size:0.85rem;color:#E2E4EC;max-width:360px;line-height:1.6;">
                    AI-generated content, CMO-reviewed and scheduled — every week, without manual input.
                </div>
            </div>
            <div style="font-size:0.68rem;color:#E2E4EC;letter-spacing:0.05em;">
                QUANTGLOBAL · NOIDA ELECTRONIC CITY
            </div>
        </div>
        """, unsafe_allow_html=True)

    with right:
        st.markdown("""
        <div style="font-size:1.5rem;font-weight:500;color:#EDEEF2;letter-spacing:-0.02em;margin-bottom:0.4rem;padding-top:2.5rem;">Sign in</div>
        <div style="font-size:0.72rem;color:#E2E4EC;text-transform:uppercase;letter-spacing:0.1em;padding-bottom:1.5rem;border-bottom:1px solid #13141A;margin-bottom:1.5rem;">
            Autonomous marketing platform
        </div>
        """, unsafe_allow_html=True)
        username = st.text_input("Username", placeholder="admin or viewer")
        password = st.text_input("Password", type="password")
        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        if st.button("Continue", use_container_width=True):
            if check_auth(username, password):
                st.session_state.update(authenticated=True, role=username.lower(), username=username.lower())
                st.rerun()
            else:
                st.error("Invalid credentials.")

# ── Data helpers ──────────────────────────────────────────────────────────────
def load_latest_run():
    ptr = OUTPUT_DIR / "latest.json"
    try:
        if ptr.exists():
            ref = json.loads(ptr.read_text(encoding="utf-8"))
            run_file = OUTPUT_DIR / Path(ref["path"]).name
            if run_file.exists():
                return json.loads(run_file.read_text(encoding="utf-8"))
        files = sorted(OUTPUT_DIR.glob("run_*.json"), reverse=True)
        return json.loads(files[0].read_text(encoding="utf-8")) if files else None
    except Exception:
        return None

def load_json_file(path: Path, default):
    try:
        if path.exists(): return json.loads(path.read_text(encoding="utf-8"))
    except Exception: pass
    return default

def format_score(score):
    if score >= 8: return "text-green", "badge-clear", "[ PASS ]"
    if score >= 7: return "text-amber", "badge-warn", "[ WARN ]"
    return "text-red", "badge-fail", "[ FAIL ]"

# ── Pipeline runner helper ────────────────────────────────────────────────────
def _run_pipeline_now():
    import importlib, sys
    sys.path.insert(0, str(Path(__file__).parent))
    with st.status("Running pipeline — extracting trending topics...", expanded=True) as status:
        try:
            import pipeline as pl
            importlib.reload(pl)
            st.write("Fetching market data and generating content...")
            pl.run_pipeline()
            status.update(label="Pipeline complete.", state="complete")
            st.rerun()
        except Exception as e:
            status.update(label=f"Execution fault: {e}", state="error")
            st.error(f"Pipeline error: {e}")

# ── Dashboard ─────────────────────────────────────────────────────────────────
def render_dashboard():
    st.markdown(BRAND_CSS, unsafe_allow_html=True)

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(f"""
        <div style="padding:1.5rem 0 1rem;">
            <div style="font-size:0.68rem;font-weight:700;letter-spacing:0.25em;text-transform:uppercase;color:#C9A84C;">
                QUANT<span style="color:rgba(201,168,76,0.3);">PULSE</span>
            </div>
            <div style="font-size:0.58rem;letter-spacing:0.15em;text-transform:uppercase;color:#E2E4EC;margin-top:0.25rem;">QuantGlobal</div>
        </div>
        <div style="border-top:1px solid rgba(255,255,255,0.04);padding-top:0.85rem;margin-bottom:0.85rem;">
            <div style="font-size:0.58rem;letter-spacing:0.1em;text-transform:uppercase;color:#E2E4EC;">{st.session_state.username}</div>
        </div>""", unsafe_allow_html=True)
        tab = st.radio(
            "Navigation",
            ["Dashboard", "Content", "ROI",
             "Market Data", "Series Arc", "Content Calendar",
             "Logs"],
            label_visibility="collapsed"
        )
        st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
        if st.button("Sign out", use_container_width=True):
            st.session_state.clear()
            st.rerun()
        
        if st.button("◀ Hide" if st.session_state.sidebar_state == "expanded" else "▶ Show"):
            st.session_state.sidebar_state = "collapsed" if st.session_state.sidebar_state == "expanded" else "expanded"
            st.rerun()

    # ── Auto-trigger: run once per login session (admin only) ──────────────
    if st.session_state.role == "admin":
        if not st.session_state.get("pipeline_ran_this_session"):
            st.session_state.pipeline_ran_this_session = True  # set BEFORE run to prevent rerun loop
            _run_pipeline_now()

    # ── Load run data ─────────────────────────────────────────────────────────
    run = load_latest_run()

    # ── Manual re-run button (sidebar, admin only) ────────────────────────────
    if st.session_state.role == "admin":
        with st.sidebar:
            st.divider()
            if st.button("Run pipeline", use_container_width=True):
                _run_pipeline_now()

    # ══ EXECUTIVE TELEMETRY ══════════════════════════════════════════════════
    if tab == "Dashboard":
        st.markdown("""
        <div class="qp-header">
            <h1>Dashboard</h1>
        </div>""", unsafe_allow_html=True)

        if not run:
            st.warning("No operational parameters found. Await next execution cycle.")
            return

        st.markdown('<div style="font-size:0.65rem;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;color:#E2E4EC;margin-bottom:1rem;">Pipeline Status</div>', unsafe_allow_html=True)
        col_a, col_b, col_c, col_d = st.columns(4)
        
        scores = run.get("cmo_scores", {})
        avg_score = round(sum(scores.values()) / max(len(scores), 1), 1) if scores else 0
        score_css, badge_css, badge_txt = format_score(avg_score)
        
        with col_a:
            st.markdown(f"""
            <div class="metric-box">
                <div class="metric-label">CMO Gate Quality</div>
                <div class="metric-value {score_css}">{avg_score} / 10</div>
                <div class="status-badge {badge_css}">{badge_txt}</div>
            </div>""", unsafe_allow_html=True)
            
        with col_b:
            safety = run.get("brand_safety", {})
            is_safe = safety.get("overall_safe", True)
            s_css = "text-green" if is_safe else "text-red"
            sb_css = "badge-clear" if is_safe else "badge-fail"
            s_txt = "COMPLIANT" if is_safe else "FLAGS ISOLATED"
            st.markdown(f"""
            <div class="metric-box">
                <div class="metric-label">SEBI Firewall</div>
                <div class="metric-value {s_css}">{s_txt}</div>
                <div class="status-badge {sb_css}">{"CLEAR" if is_safe else "FLAGGED"}</div>
            </div>""", unsafe_allow_html=True)
            
        with col_c:
            series = run.get("series_state", {})
            st.markdown(f"""
            <div class="metric-box">
                <div class="metric-label">Narrative Position</div>
                <div class="metric-value text-gold">Week {series.get('week', '—')} / 4</div>
                <div class="metric-sub">{series.get('current',{}).get('angle','')}</div>
            </div>""", unsafe_allow_html=True)
            
        with col_d:
            revisions = max(0, len(run.get("revision_log", [])) - 1)
            st.markdown(f"""
            <div class="metric-box">
                <div class="metric-label">Feedback Loops</div>
                <div class="metric-value">0{revisions}</div>
                <div class="metric-sub">Autonomous Revisions</div>
            </div>""", unsafe_allow_html=True)

        topic = run.get('selected_topic', 'No topic found')
        st.markdown(f'''<div style="margin:1.5rem 0 0.75rem;font-size:0.62rem;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;color:#E2E4EC;">This week&#39;s topic</div>
        <div style="background:#0b0c10;border:1px solid #14151c;border-radius:5px;padding:1.1rem 1.25rem;">
            <div style="font-size:0.92rem;font-weight:500;color:#EDEEF2;line-height:1.4;">{topic}</div>
            <div style="font-size:0.62rem;color:#E2E4EC;margin-top:0.4rem;text-transform:uppercase;letter-spacing:0.07em;">Auto-extracted · trending quant finance</div>
        </div>''', unsafe_allow_html=True)

    # ══ CONTENT MATRIX ═══════════════════════════════════════════════════════
    elif tab == "Content":
        st.markdown("""
        <div class="qp-header">
            <h1>Content</h1>
        </div>""", unsafe_allow_html=True)

        if not run: 
            st.warning("Awaiting compilation parameters."); st.stop()
            
        scores = run.get("cmo_scores", {})
        series = run.get("series_state", {})
        
        if series:
            current = series.get("current", {})
            arc_title = series.get('arc_title', '')
            week = series.get('week', 1)
            angle = current.get('angle', '')
            hook = current.get('hook', '')
            st.markdown(f"""
            <div style="background:#0D0E13;border:1px solid #13141A;border-radius:6px;padding:1.25rem 1.5rem;margin-bottom:1.5rem;">
                <div style="font-size:0.68rem;color:#E2E4EC;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.6rem;">Campaign Arc</div>
                <div style="font-size:1rem;font-weight:500;color:#EDEEF2;margin-bottom:1rem;">{arc_title}</div>
                <div style="display:flex;gap:2rem;flex-wrap:wrap;">
                    <div><span style="font-size:0.65rem;color:#E2E4EC;text-transform:uppercase;letter-spacing:0.08em;">Week</span><br><span style="color:#BFA050;font-size:0.9rem;">{week} of 4</span></div>
                    <div><span style="font-size:0.65rem;color:#E2E4EC;text-transform:uppercase;letter-spacing:0.08em;">Angle</span><br><span style="color:#B0B4C0;font-size:0.9rem;">{angle}</span></div>
                </div>
                {f'<div style="margin-top:1rem;padding-top:1rem;border-top:1px solid #13141A;font-size:0.85rem;color:#4A4D5C;font-style:italic;">{hook}</div>' if hook else ''}
            </div>""", unsafe_allow_html=True)

        t1, t2, t3 = st.tabs(["LinkedIn", "Twitter / X", "Hiring Ad"])
        
        with t1:
            s = scores.get("linkedin", 0)
            score_color = "#3ECF8E" if s >= 8 else "#BFA050" if s >= 7 else "#F87171"
            st.markdown(f'<div style="font-size:0.72rem;color:#E2E4EC;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:0.5rem;">CMO Score <span style="color:{score_color};font-size:1rem;font-weight:500;">{s}/10</span></div>', unsafe_allow_html=True)
            series_week = series.get("week", 1) if series else 1
            chart_path = Path(f"data/outputs/assets/mkt_chart_{series_week}.png")
            if chart_path.exists():
                st.image(str(chart_path), use_container_width=True)
            st.markdown(run.get("content",{}).get("linkedin","No content"))
                
        with t2:
            s = scores.get("twitter", 0)
            score_color = "#3ECF8E" if s >= 8 else "#BFA050" if s >= 7 else "#F87171"
            st.markdown(f'<div style="font-size:0.72rem;color:#E2E4EC;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:0.5rem;">CMO Score <span style="color:{score_color};font-size:1rem;font-weight:500;">{s}/10</span></div>', unsafe_allow_html=True)
            st.markdown(run.get("content",{}).get("twitter","No content"))
                
        with t3:
            s = scores.get("hiring", 0)
            score_color = "#3ECF8E" if s >= 8 else "#BFA050" if s >= 7 else "#F87171"
            st.markdown(f'<div style="font-size:0.72rem;color:#E2E4EC;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:0.5rem;">CMO Score <span style="color:{score_color};font-size:1rem;font-weight:500;">{s}/10</span></div>', unsafe_allow_html=True)
            st.markdown(run.get("content",{}).get("hiring_ad","No content"))

    # ══ PERFORMANCE ROI ══════════════════════════════════════════════════════
    elif tab == "ROI":
        st.markdown("""
        <div class="qp-header">
            <h1>ROI</h1>
            <p>Reach and cost estimates</p>
        </div>""", unsafe_allow_html=True)

        if not run: st.warning("Awaiting Compilation."); return
        roi = run.get("roi_metrics", {})
        if not roi: st.info("No ROI data yet — run the pipeline first."); return

        br = roi.get("brand", {})
        cst = roi.get("cost", {})

        st.markdown('<div style="font-size:0.65rem;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;color:#E2E4EC;margin-bottom:1rem;">Overview</div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"""
            <div class="metric-box">
                <div class="metric-label">Cross-Channel Impressions</div>
                <div class="metric-value text-gold">{br.get('total_impressions_min',0):,} - {br.get('total_impressions_max',0):,}</div>
                <div class="metric-sub">Aggregated Pipeline Reach</div>
            </div>""", unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div class="metric-box">
                <div class="metric-label">Capital Saved</div>
                <div class="metric-value text-green">INR {cst.get('cost_saved_inr',0):,}</div>
                <div class="metric-sub">Agency Equivalent Reduction</div>
            </div>""", unsafe_allow_html=True)
        with c3:
            st.markdown(f"""
            <div class="metric-box">
                <div class="metric-label">ROI Multiple</div>
                <div class="metric-value text-amber">{cst.get('roi_multiple',0)}x</div>
                <div class="metric-sub">Cost vs Infrastructure Spend</div>
            </div>""", unsafe_allow_html=True)

        st.markdown('<div style="font-size:0.65rem;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;color:#E2E4EC;margin:1.5rem 0 0.75rem;">Analytics summary</div>', unsafe_allow_html=True)
        summary_text = run.get("analytics", {}).get("summary", "No analytics available.")
        st.markdown(f'<div style="background:#0D0E13;border:1px solid #13141A;border-radius:6px;padding:1.25rem 1.5rem;font-size:0.9rem;color:#8A8E9E;line-height:1.7;">{summary_text}</div>', unsafe_allow_html=True)

    # ══ MARKET DYNAMICS ══════════════════════════════════════════════════════
    elif tab == "Market Data":
        st.markdown("""
        <div class="qp-header">
            <h1>Market Data</h1>
            <p>Live indices and quant equities</p>
        </div>""", unsafe_allow_html=True)

        if not run: st.warning("Awaiting Compilation."); return
        md = run.get("market_data", {})
        
        if not md or md.get("fallback") or md.get("error"):
            st.error("Market API integration offline. Generating via structured fallbacks.")
            return

        indices = {k: v for k, v in md.items() if k in ["NIFTY50", "NIFTY_BANK", "SENSEX"]}
        cols = st.columns(len(indices))
        
        for col, (name, d) in zip(cols, indices.items()):
            chg = d.get('change', 0)
            c_css = "text-green" if chg >= 0 else "text-red"
            c_dir = "[ UP ]" if chg >= 0 else "[ DOWN ]"
            sign = "+" if chg >= 0 else "−"
            col.markdown(f"""
            <div class="metric-box">
                <div class="metric-label">{name.replace('_', ' ')}</div>
                <div class="metric-value">{d.get('price', 0):,.2f}</div>
                <div class="metric-sub {c_css}" style="font-weight:500;">{sign}{abs(chg)}%</div>
            </div>""", unsafe_allow_html=True)

        if md.get("quant_stocks"):
            st.write("---")
            st.markdown('<div style="font-size:0.65rem;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;color:#E2E4EC;margin:1.5rem 0 1rem;">Equities</div>', unsafe_allow_html=True)
            scols = st.columns(len(md["quant_stocks"]))
            for col, (name, d) in zip(scols, md["quant_stocks"].items()):
                chg = d.get('change', 0)
                c_css = "text-green" if chg >= 0 else "text-red"
                c_dir = "[ UP ]" if chg >= 0 else "[ DOWN ]"
                sign = "+" if chg >= 0 else "−"
                col.markdown(f"""
                <div class="metric-box">
                    <div class="metric-label">{name.replace('_', ' ')}</div>
                    <div class="metric-value">{d.get('price', 0):,.2f}</div>
                    <div class="metric-sub {c_css}" style="font-weight:500;">{sign}{abs(chg)}%</div>
                </div>""", unsafe_allow_html=True)

    # ══ SERIES ARC TIMELINE ══════════════════════════════════════════════════
    elif tab == "Series Arc":
        st.markdown("""
        <div class="qp-header">
            <h1>Series Arc</h1>
            <p>4-week content campaign</p>
        </div>""", unsafe_allow_html=True)

        if not run: 
            st.warning("Awaiting compilation parameters."); return

        series_data = load_json_file(SERIES_FILE, {})
        if not series_data:
            st.info("No active series arc data found in current state.")
        else:
            current_week = series_data.get("week", 1)
            
            st.markdown(f"### Campaign: {series_data.get('arc_title', '')}")
            st.caption(f"{series_data.get('arc_summary', '')}")
            st.write("---")

            for week_entry in series_data.get("arc", []):
                w = week_entry.get("week", 1)
                is_curr = w == current_week
                is_done = w < current_week

                if is_curr:
                    border_color = "#FBBF24" # QuantGlobal Yellow
                    status_text = "[ ACTIVE WEEK ]"
                    text_color = "#FBBF24"
                elif is_done:
                    border_color = "#10B981" 
                    status_text = "[ COMPLETED ]"
                    text_color = "#10B981"
                else:
                    border_color = "#1E293B" 
                    status_text = "[ PENDING ]"
                    text_color = "#64748B"

                st.markdown(f"""
                <div style="background:#0D0E13; border-left: 3px solid {border_color}; border-radius: 4px; padding: 1.1rem 1.25rem; margin-bottom: 0.75rem; border-right: 1px solid #13141A; border-top: 1px solid #13141A; border-bottom: 1px solid #13141A;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                        <span style="color: {text_color}; font-weight: 600; font-size: 0.9rem; text-transform: uppercase;">Week {w}: {week_entry.get('angle', '')}</span>
                        <span style="color: {text_color}; font-size: 0.65rem; font-weight: 600; font-family: monospace;">{status_text}</span>
                    </div>
                    <div style="color: #E2E8F0; font-size: 0.85rem; margin-bottom: 0.3rem;">
                        <span style="color: #64748B; font-weight: 600;">EXECUTION HOOK:</span> <i>{week_entry.get('hook', '')}</i>
                    </div>
                    <div style="color: #E2E8F0; font-size: 0.85rem;">
                        <span style="color: #64748B; font-weight: 600;">CORE MESSAGE:</span> {week_entry.get('key_message', '')}
                    </div>
                </div>
                """, unsafe_allow_html=True)

    # ══ CONTENT CALENDAR ═════════════════════════════════════════════════════
    elif tab == "Content Calendar":
        st.markdown("""
        <div class="qp-header">
            <h1>Content Calendar</h1>
            <p>7-day publishing schedule</p>
        </div>""", unsafe_allow_html=True)

        if not run: 
            st.warning("Awaiting Compilation."); return
            
        st.markdown("### 7-Day Publishing Trajectory")
        schedule_text = run.get("schedule", "No schedule generated.")
        st.markdown(schedule_text)

    # ══ SYSTEM LOGS & GOVERNANCE ════════════════════════════════════════════
    elif tab == "Logs":
        st.markdown("""
        <div class="qp-header">
            <h1>System Logs</h1>
            <p>Pipeline execution trace</p>
        </div>""", unsafe_allow_html=True)

        if not run: st.warning("Awaiting Compilation."); return

        col1, col2 = st.columns([1, 1])
        with col1:
            st.markdown("#### Engine Execution Trace")
            
            # Cleanly strip emojis out of the raw logs for the enterprise terminal view
            clean_logs = []
            for log in run.get("status_log", []):
                msg = log['msg']
                for e, sub in [('✅', '[ OK ]'), ('🧠', '[ MEM ]'), ('🔍', '[ RSRCH ]'), ('📈', '[ MKT ]'), ('🎯', '[ TGT ]'), ('📚', '[ ARC ]'), ('✍️', '[ GEN ]'), ('🛡️', '[ SEC ]'), ('🧑‍💼', '[ CMO ]'), ('🔄', '[ LOOP ]'), ('📅', '[ SCHED ]'), ('📤', '[ DIST ]'), ('👥', '[ HR ]'), ('📊', '[ ANLY ]'), ('💰', '[ ROI ]'), ('📄', '[ DOC ]'), ('💾', '[ SAV ]'), ('⚠️', '[ WARN ]'), ('❌', '[ FAIL ]')]:
                    msg = msg.replace(e, sub)
                clean_logs.append(f"<div style='font-family:monospace;font-size:0.75rem;color:#94A3B8;border-bottom:1px solid #1E293B;padding:0.4rem 0;'>[{log['time'][11:19]}] {msg}</div>")
            
            st.markdown(f"<div style='background:#07080B;border:1px solid #13141A;padding:1rem;height:300px;overflow-y:auto;border-radius:4px;'>{''.join(clean_logs)}</div>", unsafe_allow_html=True)

        with col2:
            st.markdown("#### System Fail-Safes Active")
            st.markdown("""
            <div class="metric-box" style="padding: 1rem; margin-bottom: 0.5rem;">
                <div class="metric-label">API Rate Limit Guardian</div>
                <div class="metric-sub text-green">[ ACTIVE ] Zero-token semantic fallbacks ready</div>
            </div>
            <div class="metric-box" style="padding: 1rem; margin-bottom: 0.5rem;">
                <div class="metric-label">Graph Infinity Loop Protection</div>
                <div class="metric-sub text-green">[ ACTIVE ] Capped at 3 conditional cycles</div>
            </div>
            <div class="metric-box" style="padding: 1rem;">
                <div class="metric-label">Content Memory Filter</div>
                <div class="metric-sub text-green">[ ACTIVE ] Duplicate topic rejection enforced</div>
            </div>
            """, unsafe_allow_html=True)

# ── Main Loop ─────────────────────────────────────────────────────────────────
def main():
    st.set_page_config(
    page_title="QuantPulse — QuantGlobal",
    layout="wide",
    initial_sidebar_state=st.session_state.sidebar_state
)
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        login_screen()
    else:
        render_dashboard()

if __name__ == "__main__":
    main()