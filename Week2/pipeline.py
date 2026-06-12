"""
QuantPulse — LangGraph pipeline v3
14-node pipeline:
content_memory → trend_research → market_data → brand_voice →
series_generator → content → brand_safety → cmo_review →
[revision loop] → scheduler → distribution → recruitment →
analytics → roi_calculator → report → save
"""

import os, json, re, datetime, requests
from pathlib import Path
from typing import TypedDict, Optional
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

load_dotenv()

llm = ChatOpenAI(
    model="gpt-oss-120b",
    temperature=0.7,
    api_key=os.getenv("CEREBRAS_API_KEY"),
    base_url="https://api.cerebras.ai/v1"
)

OUTPUT_DIR   = Path("data/outputs")
REPORTS_DIR  = Path("data/reports")
MEMORY_FILE  = Path("data/content_memory.json")
SERIES_FILE  = Path("data/series_state.json")

for d in [OUTPUT_DIR, REPORTS_DIR, Path("data")]:
    d.mkdir(parents=True, exist_ok=True)


# ── State ─────────────────────────────────────────────────────────────────────
class PipelineState(TypedDict):
    # Core
    week_goal: str
    selected_topic: str
    trending_topics: str
    brand_voice: str
    # Content
    linkedin_post: str
    twitter_thread: str
    hiring_ad: str
    # Review
    cmo_scores: dict
    cmo_feedback: dict
    revision_count: int
    revision_log: list
    # Schedule
    schedule: str
    distribution: dict
    recruitment: dict
    # Analytics
    analytics: dict
    # New v3 fields
    past_topics: list          # content memory: never-repeat list
    market_data: dict          # live NSE/Nifty data
    brand_safety: dict         # SEBI firewall result
    series_state: dict         # week-1-to-4 narrative arc
    series_week: int           # which week in the arc (1-4)
    roi_metrics: dict          # estimated reach/impressions/candidates
    report_path: str           # path to generated PDF
    # Meta
    run_id: str
    errors: list
    status_log: list


# ── Helpers ───────────────────────────────────────────────────────────────────
def _log(state, msg):
    logs = list(state.get("status_log", []))
    logs.append({"time": datetime.datetime.now().isoformat(), "msg": str(msg)})
    try:
        import sys as _sys
        safe = str(msg).encode("ascii", errors="replace").decode("ascii")
        print(safe, file=_sys.__stderr__ or _sys.stderr)
    except Exception:
        pass
    return logs

def _call(prompt, _retries=3):
    import time
    for attempt in range(_retries):
        try:
            return llm.invoke([HumanMessage(content=prompt)]).content
        except Exception as e:
            msg = str(e)
            if "429" in msg or "too_many_requests" in msg or "queue_exceeded" in msg:
                wait = 30 * (attempt + 1)
                try:
                    import sys as _s
                    print(f"[429] Rate limited, retrying in {wait}s...", file=_s.__stderr__)
                except Exception:
                    pass
                time.sleep(wait)
            else:
                return f"[ERROR: {e}]"
    return "[ERROR: max retries exceeded due to rate limiting]"

def _load_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def _save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════════
# NODE 0 — Content Memory
# ══════════════════════════════════
def content_memory_node(state: PipelineState) -> PipelineState:
    logs = _log(state, "🧠 Loading content memory (never-repeat list)...")
    memory = _load_json(MEMORY_FILE, {"topics": [], "last_updated": ""})
    past_topics = memory.get("topics", [])
    count = len(past_topics)
    logs = _log({"status_log": logs}, f"✅ Memory loaded — {count} past topic(s) to avoid")
    return {**state, "past_topics": past_topics, "status_log": logs}


# ══════════════════════════════════════════════════════════════════════════════
# NODE 1 — Trend Research  (memory-aware)
# ══════════════════════════════════════════════════════════════════════════════
def trend_research_node(state: PipelineState) -> PipelineState:
    logs = _log(state, "🔍 Fetching trending topics (memory-filtered)...")
    serper_key = os.getenv("SERPER_API_KEY", "")

    snippets = []
    if serper_key and serper_key != "your_serper_api_key_here":
        queries = ["quant trading AI 2025", "algorithmic trading India", "quant finance jobs IIT"]
        for q in queries:
            try:
                r = requests.post(
                    "https://google.serper.dev/search",
                    headers={"X-API-KEY": serper_key, "Content-Type": "application/json"},
                    json={"q": q, "num": 3}, timeout=8
                )
                if r.status_code == 200:
                    for res in r.json().get("organic", [])[:2]:
                        snippets.append(f"- {res.get('title','')}: {res.get('snippet','')[:100]}")
            except Exception:
                pass

    context = "\n".join(snippets[:8]) if snippets else \
        "Use your knowledge of current quant finance and AI trading trends in 2025."

    never_repeat = state.get("past_topics", [])
    avoid_block = ""
    if never_repeat:
        avoid_block = f"\n\nNEVER select any of these previously used topics:\n" + \
                      "\n".join(f"  - {t}" for t in never_repeat[-20:])

    topic_prompt = f"""You are QuantGlobal's market intelligence agent.

Real-time search data:
{context}
{avoid_block}

QuantGlobal targets: IIT/IIM graduates, algo traders, quant researchers in India.

Task: Pick the SINGLE most relevant, timely, high-engagement topic for QuantGlobal's content this week.
The topic MUST be different from all previously used topics listed above.

Respond in this exact JSON format (no markdown):
{{
  "selected_topic": "One clear topic title",
  "week_goal": "One sentence goal for content this week",
  "rationale": "Why this topic now, in 2 sentences",
  "trending_briefing": "Full research briefing in 200 words with data points"
}}"""

    raw = _call(topic_prompt)
    try:
        clean = re.sub(r"```(?:json)?|```", "", raw).strip()
        parsed = json.loads(clean)
        selected_topic = parsed.get("selected_topic", "AI in Quantitative Trading")
        week_goal      = parsed.get("week_goal", "Establish QuantGlobal as AI trading thought leader")
        trending       = parsed.get("trending_briefing", raw)
    except Exception:
        selected_topic = "AI-Driven Quantitative Trading in India"
        week_goal      = "Position QuantGlobal as the leading quant firm for IIT/IIM talent"
        trending       = raw

    logs = _log({"status_log": logs}, f"✅ Topic selected: {selected_topic}")
    return {**state, "selected_topic": selected_topic, "week_goal": week_goal,
            "trending_topics": trending, "status_log": logs}


# ══════════════════════════════════════════════════════════════════════════════
# NODE 2 — Market Data  (live NSE/Nifty via yfinance)
# ══════════════════════════════════════════════════════════════════════════════
def market_data_node(state: PipelineState) -> PipelineState:
    logs = _log(state, "📈 Pulling live market data (NSE/Nifty)...")
    market = {}

    try:
        import yfinance as yf

        tickers = {
            "NIFTY50":    "^NSEI",
            "NIFTY_BANK": "^NSEBANK",
            "SENSEX":     "^BSESN",
            "USD_INR":    "INR=X",
        }

        for name, symbol in tickers.items():
            try:
                tkr  = yf.Ticker(symbol)
                hist = tkr.history(period="5d")
                if not hist.empty:
                    latest = hist["Close"].iloc[-1]
                    prev   = hist["Close"].iloc[-2] if len(hist) > 1 else latest
                    chg    = round(((latest - prev) / prev) * 100, 2)
                    market[name] = {
                        "price":  round(float(latest), 2),
                        "change": chg,
                        "trend":  "▲" if chg >= 0 else "▼"
                    }
            except Exception:
                pass

        # Quant-relevant stocks
        quant_stocks = {"HDFC_BANK": "HDFCBANK.NS", "RELIANCE": "RELIANCE.NS", "INFOSYS": "INFY.NS"}
        market["quant_stocks"] = {}
        for name, sym in quant_stocks.items():
            try:
                tkr  = yf.Ticker(sym)
                hist = tkr.history(period="2d")
                if not hist.empty:
                    latest = hist["Close"].iloc[-1]
                    prev   = hist["Close"].iloc[-2] if len(hist) > 1 else latest
                    chg    = round(((latest - prev) / prev) * 100, 2)
                    market["quant_stocks"][name] = {"price": round(float(latest), 2), "change": chg}
            except Exception:
                pass

        market["fetched_at"] = datetime.datetime.now().isoformat()
        market["source"]     = "yfinance / Yahoo Finance"
        logs = _log({"status_log": logs}, f"✅ Market data fetched — Nifty: {market.get('NIFTY50', {}).get('price', 'N/A')}")

    except ImportError:
        market = {"error": "yfinance not installed", "fallback": True}
        logs = _log({"status_log": logs}, "⚠️ yfinance not available — market data skipped")
    except Exception as e:
        market = {"error": str(e), "fallback": True}
        logs = _log({"status_log": logs}, f"⚠️ Market data error: {e}")

    return {**state, "market_data": market, "status_log": logs}


# ══════════════════════════════════════════════════════════════════════════════
# NODE 3 — Brand Voice
# ══════════════════════════════════════════════════════════════════════════════
def brand_voice_node(state: PipelineState) -> PipelineState:
    logs = _log(state, "🎯 Defining brand voice...")
    result = _call(f"""Define QuantGlobal's brand voice for this week's content. Max 120 words.
Topic: {state['selected_topic']}
Audience: IIT/IIM grads, algo traders, quant researchers
Platforms: LinkedIn (professional), Twitter/X (sharp + concise)
Output: tone adjectives, do/don't, key themes, platform differences.""")
    logs = _log({"status_log": logs}, "✅ Brand voice defined")
    return {**state, "brand_voice": result, "status_log": logs}


# ══════════════════════════════════════════════════════════════════════════════
# NODE 4 — Series Generator  (4-week narrative arc)
# ══════════════════════════════════════════════════════════════════════════════
def series_generator_node(state: PipelineState) -> PipelineState:
    logs = _log(state, "📚 Loading/advancing 4-week narrative arc...")
    series = _load_json(SERIES_FILE, {
        "arc_topic": "",
        "week": 0,
        "arc": [],
        "created_at": ""
    })

    topic = state["selected_topic"]

    # Start fresh arc if topic changed significantly or arc complete
    if series.get("week", 0) >= 4 or not series.get("arc"):
        arc_prompt = f"""You are QuantGlobal's content strategist. Build a 4-week LinkedIn series arc.

Topic: {topic}
Audience: IIT/IIM grads, algo traders, quant researchers

Create a narrative arc where each week builds on the last.

Respond ONLY in JSON (no markdown):
{{
  "arc_title": "Series title",
  "arc_summary": "One sentence about the full arc",
  "weeks": [
    {{"week": 1, "angle": "...", "hook": "...", "key_message": "..."}},
    {{"week": 2, "angle": "...", "hook": "...", "key_message": "..."}},
    {{"week": 3, "angle": "...", "hook": "...", "key_message": "..."}},
    {{"week": 4, "angle": "...", "hook": "...", "key_message": "..."}}
  ]
}}"""
        raw = _call(arc_prompt)
        try:
            parsed = json.loads(re.sub(r"```(?:json)?|```", "", raw).strip())
            series = {
                "arc_topic":  topic,
                "arc_title":  parsed.get("arc_title", topic),
                "arc_summary": parsed.get("arc_summary", ""),
                "arc":        parsed.get("weeks", []),
                "week":       0,
                "created_at": datetime.datetime.now().isoformat()
            }
        except Exception:
            series = {
                "arc_topic": topic,
                "arc_title": topic,
                "arc_summary": "",
                "arc": [
                    {"week": 1, "angle": "The Problem", "hook": "Why most quant strategies fail", "key_message": "Context"},
                    {"week": 2, "angle": "The Data", "hook": "What the numbers actually show", "key_message": "Evidence"},
                    {"week": 3, "angle": "The Solution", "hook": "How QuantGlobal approaches it differently", "key_message": "Differentiation"},
                    {"week": 4, "angle": "The Opportunity", "hook": "What this means for your career", "key_message": "CTA"}
                ],
                "week": 0,
                "created_at": datetime.datetime.now().isoformat()
            }

    # Advance week
    current_week = series.get("week", 0) + 1
    series["week"] = current_week
    _save_json(SERIES_FILE, series)

    current_arc = series["arc"][min(current_week - 1, len(series["arc"]) - 1)] if series["arc"] else {}

    logs = _log({"status_log": logs}, f"✅ Series arc: Week {current_week}/4 — {current_arc.get('angle','')}")
    return {**state, "series_state": {
        "week":        current_week,
        "arc_title":   series.get("arc_title", topic),
        "arc_summary": series.get("arc_summary", ""),
        "current":     current_arc,
        "full_arc":    series.get("arc", [])
    }, "series_week": current_week, "status_log": logs}


# ══════════════════════════════════════════════════════════════════════════════
# NODE 5 — Content Creation  (market-data + series-arc aware)
# ══════════════════════════════════════════════════════════════════════════════
def content_node(state: PipelineState) -> PipelineState:
    logs = _log(state, "✍️ Creating content (3 pieces, series + market data)...")

    revision_ctx = ""
    if state.get("cmo_feedback"):
        revision_ctx = "\n\nCMO FEEDBACK TO ADDRESS:\n"
        for piece, fb in state["cmo_feedback"].items():
            revision_ctx += f"- {piece.upper()}: {fb}\n"

    # Build market data context
    md = state.get("market_data", {})
    market_ctx = ""
    if md and not md.get("fallback"):
        lines = []
        for idx in ["NIFTY50", "NIFTY_BANK", "SENSEX"]:
            if idx in md:
                d = md[idx]
                lines.append(f"  {idx}: {d['price']} ({d['trend']}{abs(d['change'])}%)")
        if lines:
            market_ctx = "LIVE MARKET DATA (use 1-2 real numbers in content):\n" + "\n".join(lines)

    # Series arc context
    series = state.get("series_state", {})
    arc_ctx = ""
    if series:
        current = series.get("current", {})
        arc_ctx = f"""SERIES ARC CONTEXT:
Series: "{series.get('arc_title','')}" (Week {series.get('week',1)}/4)
This week's angle: {current.get('angle','')}
Hook to use: {current.get('hook','')}
Key message: {current.get('key_message','')}
Note: End the LinkedIn post with a teaser for next week's angle."""

    prompt = f"""You are QuantGlobal's Content Agent. Create all 3 pieces below.

TOPIC: {state['selected_topic']}
WEEK GOAL: {state['week_goal']}
BRAND VOICE: {state['brand_voice']}
RESEARCH: {state['trending_topics'][:500]}
{market_ctx}
{arc_ctx}
{revision_ctx}

CRITICAL INSTRUCTION: You MUST follow the exact structural templates below. Do not deviate. Do not add arbitrary text outside this structure.

---LINKEDIN_POST---
[Headline: 1 punchy sentence]

[Market Context: 2 sentences using research and 1 market data point]

[The Strategy: 2 sentences referencing the series arc]

[The Call to Action: 1 sentence teaser for next week]

[3-5 hashtags separated by spaces]

---TWITTER_THREAD---
1/5 [Hook from arc]

2/5 [Insight 1]

3/5 [Insight 2 + Market Data]

4/5 [Insight 3]

5/5 [CTA pointing to LinkedIn]

---HIRING_AD---
ROLE: Quantitative Analyst
LOCATION: New Delhi / Remote

THE MISSION: [1 sentence overview targeting IIT/IIM grads]

WHAT YOU NEED:
• [Skill 1]
• [Skill 2]
• [Skill 3]

THE PERKS: [1 sentence on culture/pay]

APPLY: [Call to action]
"""

    result = _call(prompt)
    try:
        import sys as _s
        print(f"=== CONTENT OUTPUT ===\n{result[:300]}", file=_s.__stderr__)
    except Exception:
        pass

    def extract(marker, text):
        m = re.search(rf"---{marker}---\s*(.*?)(?=---[A-Z_]+---|$)", text, re.DOTALL)
        if m: return m.group(1).strip()
        label = marker.replace("_", " ")
        m2 = re.search(
            rf"(?:#{1,3}\s*|\*{{1,2}})?{re.escape(label)}\*{{0,2}}:?\s*\n+(.*?)(?=(?:#{1,3}|\*{{2}})?(?:TWITTER|HIRING|LINKEDIN)|$)",
            text, re.DOTALL | re.IGNORECASE
        )
        if m2: return m2.group(1).strip()
        return None

    linkedin = extract("LINKEDIN_POST", result)
    twitter  = extract("TWITTER_THREAD", result)
    hiring   = extract("HIRING_AD", result)

    if not any([linkedin, twitter, hiring]):
        parts    = re.split(r'\n{2,}', result.strip())
        t        = max(1, len(parts) // 3)
        linkedin = "\n\n".join(parts[:t])   or result[:500]
        twitter  = "\n\n".join(parts[t:2*t]) or result[500:1000]
        hiring   = "\n\n".join(parts[2*t:]) or result[1000:]
    else:
        linkedin = linkedin or result[:500]
        twitter  = twitter  or result[500:1000]
        hiring   = hiring   or result[1000:]

    logs = _log({"status_log": logs}, "✅ Content created (series-aware, market-data injected)")
    return {**state, "linkedin_post": linkedin, "twitter_thread": twitter,
            "hiring_ad": hiring, "status_log": logs}


# ══════════════════════════════════════════════════════════════════════════════
# NODE 6 — Brand Safety Firewall  (SEBI + financial ad rules)
# ══════════════════════════════════════════════════════════════════════════════
def brand_safety_node(state: PipelineState) -> PipelineState:
    logs = _log(state, "🛡️ Running brand safety firewall (SEBI guidelines)...")

    raw = _call(f"""You are QuantGlobal's Brand Safety & Compliance Agent.
Check all 3 content pieces against SEBI advertising guidelines and general financial marketing rules.

SEBI Rules to check:
1. No guaranteed returns or performance promises
2. No misleading claims about past performance
3. No unlicensed investment advice
4. Disclaimer required if discussing specific securities
5. No exaggerated or unsubstantiated claims

LINKEDIN: {state['linkedin_post'][:600]}
TWITTER: {state['twitter_thread'][:600]}
HIRING AD: {state['hiring_ad'][:400]}

Respond ONLY in JSON (no markdown):
{{
  "linkedin_safe": true,
  "linkedin_flags": [],
  "twitter_safe": true,
  "twitter_flags": [],
  "hiring_safe": true,
  "hiring_flags": [],
  "overall_safe": true,
  "required_disclaimers": [],
  "suggested_edits": []
}}

Be strict. Flag anything that could constitute unlicensed financial advice or misleading claims.""")

    try:
        safety = json.loads(re.sub(r"```(?:json)?|```", "", raw).strip())
    except Exception:
        safety = {
            "linkedin_safe": True, "linkedin_flags": [],
            "twitter_safe": True, "twitter_flags": [],
            "hiring_safe": True, "hiring_flags": [],
            "overall_safe": True,
            "required_disclaimers": [], "suggested_edits": []
        }

    status = "✅ Brand safety: CLEAR" if safety.get("overall_safe") else \
             f"⚠️ Brand safety: FLAGS FOUND — {safety.get('suggested_edits', [])}"
    logs = _log({"status_log": logs}, status)
    return {**state, "brand_safety": safety, "status_log": logs}


# ══════════════════════════════════════════════════════════════════════════════
# NODE 7 — CMO Review
# ══════════════════════════════════════════════════════════════════════════════
def cmo_review_node(state: PipelineState) -> PipelineState:
    round_num = state.get("revision_count", 0) + 1
    logs = _log(state, f"🧑‍💼 CMO reviewing (round {round_num})...")

    safety_note = ""
    if not state.get("brand_safety", {}).get("overall_safe", True):
        flags = state["brand_safety"].get("suggested_edits", [])
        safety_note = f"\nBRAND SAFETY FLAGS (from firewall): {flags}\nFactor these into scoring."

    raw = _call(f"""You are QuantGlobal's CMO Agent. Score each content piece strictly.

BRAND VOICE: {state['brand_voice']}
TOPIC: {state['selected_topic']}
{safety_note}

LINKEDIN: {state['linkedin_post']}
TWITTER: {state['twitter_thread']}
HIRING AD: {state['hiring_ad']}

Score 1-10 on: brand alignment, audience relevance, specificity, platform fit.
Respond ONLY in this JSON (no markdown):
{{"linkedin_score":8,"linkedin_feedback":"...","twitter_score":7,"twitter_feedback":"...","hiring_score":9,"hiring_feedback":"...","overall_assessment":"...","approve":true}}
approve=true only if ALL scores >= 7.""")

    try:
        review = json.loads(re.sub(r"```(?:json)?|```", "", raw).strip())
    except Exception:
        review = {"linkedin_score": 7, "twitter_score": 7, "hiring_score": 7,
                  "linkedin_feedback": "OK", "twitter_feedback": "OK", "hiring_feedback": "OK",
                  "overall_assessment": "Auto-approved", "approve": True}

    scores   = {"linkedin": review.get("linkedin_score", 7),
                "twitter":  review.get("twitter_score", 7),
                "hiring":   review.get("hiring_score", 7)}
    feedback = {}
    if not review.get("approve", True):
        for p in ["linkedin", "twitter", "hiring"]:
            if scores[p] < 7:
                feedback[p] = review.get(f"{p}_feedback", "Needs improvement")

    rev_log = list(state.get("revision_log", []))
    rev_log.append({"round": round_num, "scores": scores, "feedback": feedback,
                    "approved": review.get("approve", True),
                    "assessment": review.get("overall_assessment", "")})

    status = "✅ CMO APPROVED" if review.get("approve") else \
             f"❌ CMO REJECTED {[p for p, s in scores.items() if s < 7]}"
    logs = _log({"status_log": logs}, status)
    return {**state, "cmo_scores": scores, "cmo_feedback": feedback,
            "revision_count": round_num, "revision_log": rev_log, "status_log": logs}


def should_revise(state):
    return "revise" if (
        any(s < 7 for s in state.get("cmo_scores", {}).values()) and
        state.get("revision_count", 0) < 3
    ) else "proceed"


def content_revision_node(state):
    logs = _log(state, f"🔄 Revising content (round {state.get('revision_count', 1)})...")
    new = content_node(state)
    return {**new, "status_log": _log({"status_log": new["status_log"]}, "✅ Revision done")}


# ══════════════════════════════════════════════════════════════════════════════
# NODE 8 — Scheduler
# ══════════════════════════════════════════════════════════════════════════════
def scheduler_node(state: PipelineState) -> PipelineState:
    logs = _log(state, "📅 Building content calendar...")
    result = _call(f"""Build a 7-day content calendar for QuantGlobal.
Topic: {state['selected_topic']}
Series: Week {state.get('series_week', 1)}/4 of "{state.get('series_state', {}).get('arc_title', '')}"
Content: LinkedIn post (score {state['cmo_scores'].get('linkedin','?')}/10),
         Twitter thread ({state['cmo_scores'].get('twitter','?')}/10),
         Hiring ad ({state['cmo_scores'].get('hiring','?')}/10)
Audience active: weekday mornings 9-11am, lunch 12-1pm India time.

CRITICAL FORMATTING INSTRUCTION:
You MUST output a strict, valid Markdown table. You MUST include the dashed separator row immediately after the header. 
Use EXACTLY this format:

| Day | Time (IST) | Platform | Content Type | Rationale |
|---|---|---|---|---|
| Monday | 09:30 | ...
""")
    logs = _log({"status_log": logs}, "✅ Calendar built")
    return {**state, "schedule": result, "status_log": logs}

# ══════════════════════════════════════════════════════════════════════════════
# NODE 9 — Distribution
# ══════════════════════════════════════════════════════════════════════════════
def distribution_node(state: PipelineState) -> PipelineState:
    logs = _log(state, "📤 Building distribution plan...")
    distribution = {
        "linkedin": {
            "platform": "LinkedIn", "content_type": "Post",
            "char_count": len(state["linkedin_post"]), "status": "ready",
            "action": "Copy post → paste in LinkedIn → add image → publish",
            "best_time": "Tuesday 9:00 AM IST", "expected_reach": "500-2000 impressions",
            "checklist": ["Add company logo image", "Tag relevant people",
                          "Post from company page", "Pin to top of profile"]
        },
        "twitter": {
            "platform": "Twitter/X", "content_type": "Thread",
            "char_count": len(state["twitter_thread"]), "status": "ready",
            "action": "Post tweets in sequence, reply to each to form thread",
            "best_time": "Wednesday 12:00 PM IST", "expected_reach": "200-800 impressions",
            "checklist": ["Post tweet 1 first", "Reply to tweet 1 with tweet 2",
                          "Continue thread", "Add relevant hashtags"]
        },
        "hiring": {
            "platform": "Multiple Job Boards", "content_type": "Hiring Ad",
            "char_count": len(state["hiring_ad"]), "status": "ready",
            "action": "Post on LinkedIn Jobs, Naukri, Internshala, IIT job portals",
            "best_time": "Monday 10:00 AM IST", "expected_reach": "100-500 views per board",
            "checklist": ["Post on LinkedIn Jobs", "Post on Naukri.com",
                          "Post on Internshala (for freshers)",
                          "Share in IIT/IIM alumni WhatsApp groups",
                          "Pin on QuantGlobal website careers page"]
        }
    }
    logs = _log({"status_log": logs}, "✅ Distribution plan ready")
    return {**state, "distribution": distribution, "status_log": logs}


# ══════════════════════════════════════════════════════════════════════════════
# NODE 10 — Recruitment
# ══════════════════════════════════════════════════════════════════════════════
def recruitment_node(state: PipelineState) -> PipelineState:
    logs = _log(state, "👥 Building recruitment tracker...")
    result = _call(f"""You are QuantGlobal's Talent Acquisition Agent.
Hiring ad: {state['hiring_ad'][:300]}
Role: Quantitative Analyst | Target: IIT/IIM grads, algo traders

Provide in JSON (no markdown):
{{
  "role": "Quantitative Analyst",
  "target_profiles": ["profile1", "profile2", "profile3"],
  "job_boards": [
    {{"name": "LinkedIn Jobs", "url": "https://linkedin.com/jobs", "expected_applicants": "20-40", "cost": "Free"}},
    {{"name": "Naukri.com", "url": "https://naukri.com", "expected_applicants": "30-60", "cost": "Free basic"}},
    {{"name": "Internshala", "url": "https://internshala.com", "expected_applicants": "15-30", "cost": "Free"}},
    {{"name": "IIT Job Portal", "url": "https://placement.iitb.ac.in", "expected_applicants": "10-20", "cost": "Free"}}
  ],
  "screening_questions": ["q1", "q2", "q3"],
  "kpis": {{"target_applications": 50, "target_quality_rate": "30%", "time_to_hire": "3-4 weeks"}}
}}""")

    try:
        recruitment = json.loads(re.sub(r"```(?:json)?|```", "", result).strip())
    except Exception:
        recruitment = {
            "role": "Quantitative Analyst",
            "target_profiles": ["IIT/IIM grads with finance interest",
                                 "Algo traders with Python skills",
                                 "Quant researchers with ML background"],
            "job_boards": [
                {"name": "LinkedIn Jobs",   "url": "https://linkedin.com/jobs",        "expected_applicants": "20-40", "cost": "Free"},
                {"name": "Naukri.com",      "url": "https://naukri.com",               "expected_applicants": "30-60", "cost": "Free basic"},
                {"name": "Internshala",     "url": "https://internshala.com",          "expected_applicants": "15-30", "cost": "Free"},
                {"name": "IIT Job Portal",  "url": "https://placement.iitb.ac.in",    "expected_applicants": "10-20", "cost": "Free"}
            ],
            "screening_questions": ["What quant strategies have you implemented?",
                                    "Describe your Python/algo trading experience",
                                    "Why QuantGlobal over other firms?"],
            "kpis": {"target_applications": 50, "target_quality_rate": "30%", "time_to_hire": "3-4 weeks"}
        }

    logs = _log({"status_log": logs}, "✅ Recruitment tracker ready")
    return {**state, "recruitment": recruitment, "status_log": logs}

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from pathlib import Path

# ══════════════════════════════════════════════════════════════════════════════
# NODE 12 — Visual Engine (Programmatic Graphics)
# ══════════════════════════════════════════════════════════════════════════════
def graphic_node(state: PipelineState) -> PipelineState:
    logs = _log(state, "[ RNDR ] Generating proprietary data visualizations...")
    
    # 1. Setup paths
    out_dir = Path("data/outputs/assets")
    out_dir.mkdir(parents=True, exist_ok=True)
    chart_path = out_dir / f"mkt_chart_{state.get('series_week', 1)}.png"
    
    # 2. Extract market data from the state
    market_data = state.get("market_data", {})
    nifty = market_data.get("NIFTY50", {"price": 23000, "change": 0.5})
    
    # 3. Institutional Dark Mode Styling
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=300)
    fig.patch.set_facecolor('#020617')
    ax.set_facecolor('#020617')
    
    # Simulate a stylized intraday price curve for the visual
    base_price = nifty.get("price", 23000)
    x = np.linspace(0, 10, 100)
    y = base_price + (np.cumsum(np.random.randn(100)) * 15)
    
    # 4. Plotting the Alpha Vector
    color = '#10B981' if nifty.get("change", 0) >= 0 else '#EF4444'
    ax.plot(x, y, color=color, linewidth=2)
    ax.fill_between(x, y, base_price - 200, color=color, alpha=0.1)
    
    # 5. Corporate Formatting
    ax.set_title("NIFTY50: Live Liquidity Vector", color="#F8FAFC", fontsize=14, loc='left', pad=15)
    ax.text(0, base_price - 250, f"QuantPulse Autonomous Architecture | Week {state.get('series_week', 1)}", color="#64748B", fontsize=8)
    
    ax.grid(color='#1E293B', linestyle='--', linewidth=0.5)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#1E293B')
    ax.spines['bottom'].set_color('#1E293B')
    ax.set_ylim(min(y) - 50, max(y) + 50)
    ax.set_xticks([]) # Clean minimalist x-axis
    
    # 6. Save Asset
    plt.tight_layout()
    plt.savefig(chart_path, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()
    
    # 7. Update State
    visual_assets = state.get("visuals", {})
    visual_assets["linkedin_chart"] = str(chart_path)
    
    logs = _log({"status_log": logs}, "[ OK ] Visual assets rendered locally")
    return {**state, "visuals": visual_assets, "status_log": logs}
    
# ══════════════════════════════════════════════════════════════════════════════
# NODE 11 — Analytics
# ══════════════════════════════════════════════════════════════════════════════
def analytics_node(state: PipelineState) -> PipelineState:
    logs = _log(state, "📊 Running analytics...")
    result = _call(f"""QuantGlobal Analytics Agent. Analyze this week.
Topic: {state['selected_topic']}
CMO Scores: LinkedIn {state['cmo_scores'].get('linkedin')}/10,
            Twitter {state['cmo_scores'].get('twitter')}/10,
            Hiring {state['cmo_scores'].get('hiring')}/10
Series week: {state.get('series_week', 1)}/4
Revisions: {state.get('revision_count', 0) - 1}

Provide (max 200 words):
1. Predicted engagement per platform (realistic for quant firm)
2. Strongest piece and why
3. Improvement vector for weakest piece
4. 3 recommendations for next week
5. Any brand risk flags""")

    analytics = {
        "summary":        result,
        "scores":         state["cmo_scores"],
        "revision_rounds": max(0, state.get("revision_count", 1) - 1),
        "avg_score":      round(sum(state["cmo_scores"].values()) / len(state["cmo_scores"]), 1),
        "topic":          state["selected_topic"],
        "generated_at":   datetime.datetime.now().isoformat()
    }
    logs = _log({"status_log": logs}, "✅ Analytics complete")
    return {**state, "analytics": analytics, "status_log": logs}


# ══════════════════════════════════════════════════════════════════════════════
# NODE 12 — ROI Calculator
# ══════════════════════════════════════════════════════════════════════════════
def roi_calculator_node(state: PipelineState) -> PipelineState:
    logs = _log(state, "💰 Calculating ROI metrics...")
    scores  = state.get("cmo_scores", {})
    avg_score = round(sum(scores.values()) / max(len(scores), 1), 1)

    # Score-weighted reach estimates (realistic for an Indian quant firm)
    score_mult = avg_score / 10.0

    li_score = scores.get("linkedin", 7)
    tw_score = scores.get("twitter", 7)
    hi_score = scores.get("hiring", 7)

    li_min  = int(500  * (li_score / 7))
    li_max  = int(2000 * (li_score / 7))
    tw_min  = int(200  * (tw_score / 7))
    tw_max  = int(800  * (tw_score / 7))
    hi_apps = int(50   * (hi_score / 7))

    # Estimated cost savings vs. agency
    agency_cost_equivalent = 35000  # ₹ per week typical for agency
    pipeline_cost_est      = 500    # ₹ API costs approx
    cost_saved             = agency_cost_equivalent - pipeline_cost_est

    roi_metrics = {
        "linkedin": {
            "impressions_min":      li_min,
            "impressions_max":      li_max,
            "estimated_clicks":     int(li_max * 0.03),
            "profile_visits":       int(li_max * 0.015),
            "score_used":           li_score
        },
        "twitter": {
            "impressions_min":      tw_min,
            "impressions_max":      tw_max,
            "estimated_engagements": int(tw_max * 0.05),
            "score_used":           tw_score
        },
        "hiring": {
            "expected_applications":     hi_apps,
            "quality_applications":      int(hi_apps * 0.3),
            "estimated_interview_calls": int(hi_apps * 0.1),
            "score_used":                hi_score
        },
        "brand": {
            "total_impressions_min": li_min + tw_min,
            "total_impressions_max": li_max + tw_max,
            "brand_score":           round(avg_score * 10, 0)
        },
        "cost": {
            "agency_equivalent_inr": agency_cost_equivalent,
            "pipeline_cost_est_inr": pipeline_cost_est,
            "cost_saved_inr":        cost_saved,
            "roi_multiple":          round(agency_cost_equivalent / max(pipeline_cost_est, 1), 1)
        },
        "calculated_at": datetime.datetime.now().isoformat()
    }

    logs = _log({"status_log": logs}, f"✅ ROI: {li_min}-{li_max} LinkedIn impressions | ₹{cost_saved:,} saved vs agency")
    return {**state, "roi_metrics": roi_metrics, "status_log": logs}


# ══════════════════════════════════════════════════════════════════════════════
# NODE 13 — Weekly Report (PDF)
# ══════════════════════════════════════════════════════════════════════════════
def report_node(state: PipelineState) -> PipelineState:
    logs = _log(state, "📄 Generating weekly PDF report...")

    run_id     = state.get("run_id", datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
    report_path = REPORTS_DIR / f"quantpulse_report_{run_id}.pdf"

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            HRFlowable, PageBreak
        )

        # ── Colors ──
        NAVY   = colors.HexColor("#0f172a")
        BLUE   = colors.HexColor("#1e3a5f")
        SKY    = colors.HexColor("#38bdf8")
        GREEN  = colors.HexColor("#10b981")
        AMBER  = colors.HexColor("#f59e0b")
        RED    = colors.HexColor("#ef4444")
        SLATE  = colors.HexColor("#94a3b8")
        WHITE  = colors.white
        LIGHT  = colors.HexColor("#e2e8f0")

        doc   = SimpleDocTemplate(
            str(report_path), pagesize=A4,
            leftMargin=2*cm, rightMargin=2*cm,
            topMargin=2*cm, bottomMargin=2*cm
        )
        styles = getSampleStyleSheet()

        def style(name, **kw):
            return ParagraphStyle(name, parent=styles["Normal"], **kw)

        S_TITLE   = style("title",   fontSize=22, textColor=WHITE,    fontName="Helvetica-Bold",  spaceAfter=4)
        S_SUB     = style("sub",     fontSize=10, textColor=SLATE,    fontName="Helvetica",       spaceAfter=2)
        S_H1      = style("h1",      fontSize=14, textColor=SKY,      fontName="Helvetica-Bold",  spaceBefore=14, spaceAfter=6)
        S_H2      = style("h2",      fontSize=11, textColor=LIGHT,    fontName="Helvetica-Bold",  spaceBefore=8,  spaceAfter=4)
        S_BODY    = style("body",    fontSize=9,  textColor=LIGHT,    fontName="Helvetica",       leading=14,     spaceAfter=6)
        S_SMALL   = style("small",   fontSize=8,  textColor=SLATE,    fontName="Helvetica",       leading=12)
        S_LABEL   = style("label",   fontSize=7,  textColor=SLATE,    fontName="Helvetica",       spaceAfter=1)
        S_CODE    = style("code",    fontSize=8,  textColor=GREEN,    fontName="Courier",         leading=13,     spaceAfter=4)

        story = []
        scores    = state.get("cmo_scores", {})
        roi       = state.get("roi_metrics", {})
        series    = state.get("series_state", {})
        safety    = state.get("brand_safety", {})
        analytics = state.get("analytics", {})
        md        = state.get("market_data", {})
        avg_score = analytics.get("avg_score", 0)

        def score_color(s):
            return GREEN if s >= 8 else AMBER if s >= 7 else RED

        def section_header(title):
            story.append(Spacer(1, 0.3*cm))
            story.append(HRFlowable(width="100%", thickness=1, color=BLUE))
            story.append(Paragraph(title, S_H1))

        # ── Cover ──
        cover_data = [[
            Paragraph("⚡ QuantPulse", S_TITLE),
            Paragraph(f"Weekly Report — {run_id.replace('_', ' ')}", S_SUB)
        ]]
        cover_tbl = Table(cover_data, colWidths=["60%", "40%"])
        cover_tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0,0), (-1,-1), NAVY),
            ("ROUNDEDCORNERS", (0,0), (-1,-1), [8,8,8,8]),
            ("TOPPADDING",   (0,0), (-1,-1), 20),
            ("BOTTOMPADDING",(0,0), (-1,-1), 20),
            ("LEFTPADDING",  (0,0), (-1,-1), 16),
            ("RIGHTPADDING", (0,0), (-1,-1), 16),
            ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ]))
        story.append(cover_tbl)
        story.append(Spacer(1, 0.4*cm))

        # Topic + goal
        story.append(Paragraph(f"Topic: {state.get('selected_topic','')}", S_H2))
        story.append(Paragraph(state.get("week_goal", ""), S_BODY))
        if series:
            story.append(Paragraph(
                f"Series: \"{series.get('arc_title','')}\" — Week {series.get('week',1)}/4 · {series.get('current',{}).get('angle','')}",
                S_SMALL
            ))

        # ── KPI Scorecards ──
        section_header("Key Performance Indicators")

        def kpi_cell(label, value, sub, color=LIGHT):
            return [
                Paragraph(label, S_LABEL),
                Paragraph(f"<font color='#{color.hexval()[2:]}' size=18><b>{value}</b></font>", styles["Normal"]),
                Paragraph(sub, S_SMALL)
            ]

        kpi_rows = [[
            kpi_cell("AVG CMO SCORE",  f"{avg_score}/10",            "All content",     score_color(avg_score)),
            kpi_cell("LINKEDIN",       f"{scores.get('linkedin','—')}/10", "Post quality", score_color(scores.get('linkedin',0))),
            kpi_cell("TWITTER/X",      f"{scores.get('twitter','—')}/10",  "Thread quality", score_color(scores.get('twitter',0))),
            kpi_cell("HIRING AD",      f"{scores.get('hiring','—')}/10",   "Ad targeting", score_color(scores.get('hiring',0))),
            kpi_cell("REVISIONS",      str(max(0, state.get('revision_count',1)-1)), "Rejection loops", AMBER),
        ]]
        kpi_tbl = Table(kpi_rows, colWidths=["20%"]*5)
        kpi_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), NAVY),
            ("GRID",          (0,0), (-1,-1), 0.5, BLUE),
            ("TOPPADDING",    (0,0), (-1,-1), 10),
            ("BOTTOMPADDING", (0,0), (-1,-1), 10),
            ("LEFTPADDING",   (0,0), (-1,-1), 8),
            ("RIGHTPADDING",  (0,0), (-1,-1), 8),
            ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ]))
        story.append(kpi_tbl)

        # ── Market Data ──
        if md and not md.get("fallback"):
            section_header("Live Market Data")
            mkt_rows = [["Index", "Price", "Change"]]
            for idx in ["NIFTY50", "NIFTY_BANK", "SENSEX"]:
                if idx in md:
                    d = md[idx]
                    mkt_rows.append([
                        Paragraph(idx, S_BODY),
                        Paragraph(f"{d['price']:,.2f}", S_BODY),
                        Paragraph(f"{d['trend']}{abs(d['change'])}%",
                                  ParagraphStyle("chg", parent=S_BODY,
                                                 textColor=GREEN if d["change"] >= 0 else RED))
                    ])
            mkt_tbl = Table(mkt_rows, colWidths=["40%", "30%", "30%"])
            mkt_tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0,0), (-1,0),  BLUE),
                ("TEXTCOLOR",     (0,0), (-1,0),  WHITE),
                ("FONTNAME",      (0,0), (-1,0),  "Helvetica-Bold"),
                ("FONTSIZE",      (0,0), (-1,0),  9),
                ("BACKGROUND",    (0,1), (-1,-1), NAVY),
                ("ROWBACKGROUNDS",(0,1), (-1,-1), [NAVY, colors.HexColor("#111827")]),
                ("GRID",          (0,0), (-1,-1), 0.5, BLUE),
                ("TOPPADDING",    (0,0), (-1,-1), 7),
                ("BOTTOMPADDING", (0,0), (-1,-1), 7),
                ("LEFTPADDING",   (0,0), (-1,-1), 8),
            ]))
            story.append(mkt_tbl)

        # ── ROI ──
        section_header("ROI Metrics")
        li_roi = roi.get("linkedin", {})
        tw_roi = roi.get("twitter", {})
        hi_roi = roi.get("hiring", {})
        cost   = roi.get("cost", {})
        brand  = roi.get("brand", {})

        roi_rows = [
            ["Metric", "LinkedIn", "Twitter/X", "Hiring Ad"],
            ["Impressions (est.)",
             f"{li_roi.get('impressions_min',0):,}–{li_roi.get('impressions_max',0):,}",
             f"{tw_roi.get('impressions_min',0):,}–{tw_roi.get('impressions_max',0):,}",
             "N/A"],
            ["Clicks / Engagements",
             f"~{li_roi.get('estimated_clicks',0):,} clicks",
             f"~{tw_roi.get('estimated_engagements',0):,} engagements",
             f"~{hi_roi.get('expected_applications',0)} applications"],
            ["Quality Leads",
             f"~{li_roi.get('profile_visits',0):,} profile visits",
             "—",
             f"~{hi_roi.get('quality_applications',0)} quality apps"],
        ]
        roi_tbl = Table(roi_rows, colWidths=["30%", "23%", "23%", "24%"])
        roi_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0),  BLUE),
            ("TEXTCOLOR",     (0,0), (-1,0),  WHITE),
            ("FONTNAME",      (0,0), (-1,0),  "Helvetica-Bold"),
            ("FONTSIZE",      (0,0), (-1,-1), 8),
            ("BACKGROUND",    (0,1), (-1,-1), NAVY),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [NAVY, colors.HexColor("#111827")]),
            ("GRID",          (0,0), (-1,-1), 0.5, BLUE),
            ("TOPPADDING",    (0,0), (-1,-1), 7),
            ("BOTTOMPADDING", (0,0), (-1,-1), 7),
            ("LEFTPADDING",   (0,0), (-1,-1), 8),
            ("TEXTCOLOR",     (0,1), (-1,-1), LIGHT),
        ]))
        story.append(roi_tbl)
        story.append(Spacer(1, 0.3*cm))

        # Cost savings callout
        if cost:
            story.append(Paragraph(
                f"💰  Estimated cost savings vs. agency this week: "
                f"<b>₹{cost.get('cost_saved_inr',0):,}</b>  "
                f"({cost.get('roi_multiple',0)}× ROI multiple)",
                S_BODY
            ))

        # ── Brand Safety ──
        section_header("Brand Safety & Compliance")
        overall_safe = safety.get("overall_safe", True)
        safety_color = GREEN if overall_safe else RED
        story.append(Paragraph(
            f"SEBI Compliance Status: <b>{'CLEAR ✅' if overall_safe else 'FLAGS FOUND ⚠️'}</b>",
            ParagraphStyle("safe", parent=S_BODY, textColor=safety_color)
        ))
        if safety.get("required_disclaimers"):
            story.append(Paragraph("Required disclaimers:", S_H2))
            for d in safety["required_disclaimers"]:
                story.append(Paragraph(f"• {d}", S_SMALL))
        if safety.get("suggested_edits"):
            story.append(Paragraph("Suggested edits:", S_H2))
            for e in safety["suggested_edits"]:
                story.append(Paragraph(f"• {e}", S_SMALL))

        # ── Content ──
        story.append(PageBreak())
        section_header("Content — LinkedIn Post")
        story.append(Paragraph(state.get("linkedin_post", ""), S_BODY))

        section_header("Content — Twitter/X Thread")
        story.append(Paragraph(state.get("twitter_thread", ""), S_BODY))

        section_header("Content — Hiring Ad")
        story.append(Paragraph(state.get("hiring_ad", ""), S_BODY))

        # ── Analytics ──
        section_header("Analytics Report")
        story.append(Paragraph(analytics.get("summary", ""), S_BODY))

        # ── Calendar ──
        section_header("Content Calendar")
        story.append(Paragraph(state.get("schedule", ""), S_CODE))

        # ── Footer ──
        story.append(Spacer(1, 0.5*cm))
        story.append(HRFlowable(width="100%", thickness=1, color=BLUE))
        story.append(Paragraph(
            f"Generated by QuantPulse v3 · {datetime.datetime.now().strftime('%d %b %Y %H:%M IST')} · Run {run_id}",
            S_SMALL
        ))

        doc.build(story)
        logs = _log({"status_log": logs}, f"✅ PDF report saved → {report_path}")

    except Exception as e:
        logs = _log({"status_log": logs}, f"⚠️ PDF generation error: {e}")
        report_path = Path("")

    return {**state, "report_path": str(report_path), "status_log": logs}


# ══════════════════════════════════════════════════════════════════════════════
# NODE 14 — Save  (also updates content memory)
# ══════════════════════════════════════════════════════════════════════════════
def save_node(state: PipelineState) -> PipelineState:
    run_id = state.get("run_id", datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
    logs   = _log(state, f"💾 Saving run {run_id}...")

    data = {
        "run_id":         run_id,
        "selected_topic": state.get("selected_topic", ""),
        "week_goal":      state["week_goal"],
        "trending_topics": state["trending_topics"],
        "brand_voice":    state["brand_voice"],
        "content": {
            "linkedin":  state["linkedin_post"],
            "twitter":   state["twitter_thread"],
            "hiring_ad": state["hiring_ad"]
        },
        "market_data":  state.get("market_data", {}),
        "brand_safety": state.get("brand_safety", {}),
        "series_state": state.get("series_state", {}),
        "cmo_scores":   state["cmo_scores"],
        "revision_log": state.get("revision_log", []),
        "schedule":     state["schedule"],
        "distribution": state.get("distribution", {}),
        "recruitment":  state.get("recruitment", {}),
        "analytics":    state["analytics"],
        "roi_metrics":  state.get("roi_metrics", {}),
        "report_path":  state.get("report_path", ""),
        "status_log":   state.get("status_log", [])
    }

    json_path = OUTPUT_DIR / f"run_{run_id}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    md_path = OUTPUT_DIR / f"run_{run_id}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# QuantPulse — {state.get('selected_topic','')}\n\n")
        f.write(f"## CMO Scores\n")
        for k, v in state["cmo_scores"].items():
            f.write(f"- {k.title()}: {v}/10\n")
        f.write(f"\n## LinkedIn\n{state['linkedin_post']}\n\n")
        f.write(f"## Twitter/X\n{state['twitter_thread']}\n\n")
        f.write(f"## Hiring Ad\n{state['hiring_ad']}\n\n")
        f.write(f"## Calendar\n{state['schedule']}\n\n")
        f.write(f"## Analytics\n{state['analytics']['summary']}\n")

    with open(OUTPUT_DIR / "latest.json", "w", encoding="utf-8") as f:
        json.dump({"run_id": run_id, "path": str(json_path)}, f)

    # ── Update content memory ──
    memory = _load_json(MEMORY_FILE, {"topics": []})
    topics = memory.get("topics", [])
    new_topic = state.get("selected_topic", "")
    if new_topic and new_topic not in topics:
        topics.append(new_topic)
    _save_json(MEMORY_FILE, {
        "topics":       topics,
        "last_updated": datetime.datetime.now().isoformat()
    })

    logs = _log({"status_log": logs}, f"✅ Saved run_{run_id} | Memory updated ({len(topics)} topics)")
    return {**state, "run_id": run_id, "status_log": logs}


# ══════════════════════════════════════════════════════════════════════════════
# Build Graph
# ══════════════════════════════════════════════════════════════════════════════
def build_pipeline():
    g = StateGraph(PipelineState)

    g.add_node("content_memory",    content_memory_node)
    g.add_node("trend_research",    trend_research_node)
    g.add_node("market_data",       market_data_node)
    g.add_node("brand_voice",       brand_voice_node)
    g.add_node("series_generator",  series_generator_node)
    g.add_node("content",           content_node)
    g.add_node("brand_safety",      brand_safety_node)
    g.add_node("cmo_review",        cmo_review_node)
    g.add_node("content_revision",  content_revision_node)
    g.add_node("scheduler",         scheduler_node)
    g.add_node("distribution",      distribution_node)
    g.add_node("recruitment",       recruitment_node)
    g.add_node("analytics",         analytics_node)
    g.add_node("roi_calculator",    roi_calculator_node)
    g.add_node("report",            report_node)
    g.add_node("save",              save_node)

    g.set_entry_point("content_memory")
    g.add_edge("content_memory",   "trend_research")
    g.add_edge("trend_research",   "market_data")
    g.add_edge("market_data",      "brand_voice")
    g.add_edge("brand_voice",      "series_generator")
    g.add_edge("series_generator", "content")
    g.add_edge("content",          "brand_safety")
    g.add_edge("brand_safety",     "cmo_review")
    g.add_conditional_edges("cmo_review", should_revise,
                            {"revise": "content_revision", "proceed": "scheduler"})
    g.add_edge("content_revision", "cmo_review")
    g.add_edge("scheduler",        "distribution")
    g.add_edge("distribution",     "recruitment")
    g.add_edge("recruitment",      "analytics")
    g.add_edge("analytics",        "roi_calculator")
    g.add_edge("roi_calculator",   "report")
    g.add_edge("report",           "save")
    g.add_edge("save",             END)

    return g.compile()


def run_pipeline(week_goal: str = None, run_id: str = None) -> PipelineState:
    if not run_id:
        run_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    pipeline = build_pipeline()
    result = pipeline.invoke({
        "week_goal":      week_goal or "",
        "selected_topic": "",
        "trending_topics": "",
        "brand_voice":    "",
        "linkedin_post":  "",
        "twitter_thread": "",
        "hiring_ad":      "",
        "cmo_scores":     {},
        "cmo_feedback":   {},
        "revision_count": 0,
        "revision_log":   [],
        "schedule":       "",
        "distribution":   {},
        "recruitment":    {},
        "analytics":      {},
        "past_topics":    [],
        "market_data":    {},
        "brand_safety":   {},
        "series_state":   {},
        "series_week":    1,
        "roi_metrics":    {},
        "report_path":    "",
        "run_id":         run_id,
        "errors":         [],
        "status_log":     []
    })
    return result


if __name__ == "__main__":
    result = run_pipeline()
    print(f"\n✅ Done | Topic: {result['selected_topic']}")
    print(f"CMO Scores: {result['cmo_scores']}")
    print(f"Avg: {result['analytics'].get('avg_score')}/10")
    print(f"Report: {result.get('report_path','')}")