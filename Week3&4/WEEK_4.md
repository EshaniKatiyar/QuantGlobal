# WEEK 4 — QuantGlobal L&D + Full Integration

## Platform
LangGraph (continued from Week 3)

## Agent Roles

### L&D Team Supervisor
Manages Onboarding, Coach/Trainer, Quiz, Decision agents. Drives candidates through 4-week simulated training.

### Onboarding Agent
- Creates candidate record in SQLite with AES-256 encrypted PII (Fernet key persisted once and reused — not regenerated on every call, so decryption never breaks)
- Captures explicit consent before storing any data
- Generates Streamlit trainee credentials (bcrypt hashed passwords); the raw password is delivered to the candidate only — never printed to console or written into the audit log

### Coach/Trainer Agent
- Delivers role-branched weekly modules (Quant Researcher / Algo Trader tracks), generated fresh per trainee per week by Cerebras based on their weak topics and previous score — not a static module library

### Quiz Agent
- Cerebras generates a fresh, role-branched, weak-topic-weighted quiz each week (not a hardcoded bank) — keeps content adaptive rather than memorizable
- A separate Cerebras call plays the candidate and answers; a third call evaluates — never self-graded
- Adaptive weighting: topics scoring <60% in week N are weighted heavier in week N+1
- Week 1 early offboard checkpoint: score <60% → immediate offboard + blacklist

### Decision Agent
- Computes Alpha Score v2 (0-100) = Alpha v1 + Learning Velocity (0-25), reasoned over by Cerebras (trajectory, strengths/weaknesses) rather than pure threshold math
- Three-way decision: PPO (≥70) | Talent Pool (50-69) | Offboard+Blacklist (<50)

## Differentiating Features

### Alpha Score
Quant-framed composite signal. v1 post-screening (GitHub Signal 25 + Background Fit 25 + Assessment 25), v2 post-L&D (v1 + Learning Velocity 0-25). Background Fit tiers match Revised Plan §8: IIT/ISI/CMI = 25, Tier-2 = 15, Other = 5.

### Institutional Memory
Blacklist stores SHA-256 hashed identifiers only (no raw PII). Talent Pool stores candidate_id + re-engage date.

### Adaptive Quiz
Topic weakness tracking drives next week's question weighting and generation — not generic.

### Hiring Velocity Metric
TL sees estimated days to next hire based on active pipeline stage distribution.

### Privacy & Consent
- Explicit consent checkbox before any data stored
- AES-256 (Fernet) encryption for PII documents, key persisted across runs
- 15-day deletion for failed candidates, 60-day for offboarded
- Blacklist: hashed identifiers only
- Raw trainee passwords never logged or printed — bcrypt hash is the only thing persisted server-side

### Feedback & Continuous Improvement Loops (Revised Plan §12)
- **Loop 1 — Sourcing yield:** Sourcer tracks GitHub vs Google screening pass-through rate; higher-yield source queried harder next run. Visible on the HR dashboard.
- **Loop 2 — Score calibration:** After each cohort's L&D completes, Root compares the Alpha v1 top-quartile's average Alpha v2 outcome against the cohort average. If top screeners aren't also top L&D performers, the weights are flagged for manual review.
- **Loop 3 — Quiz topic trends:** HR dashboard surfaces cohort-level average score per topic across all trainees/weeks. Persistently low topics flag a Coach/Trainer content gap, not individual candidate quality.

## LLM Prompts Used
Cerebras (via the single shared client in `core/llm.py`) is used throughout — sourcing extraction, coaching module generation, quiz question generation + candidate-answer simulation + evaluation, and final PPO/Talent Pool/Offboard reasoning. This is a deliberate departure from a fully-deterministic L&D phase: it keeps content non-repeatable and decisions auditable but reasoned, at the cost of Cerebras inference calls (still free tier for this MVP).

## One Win
The Week 1 early offboard checkpoint works exactly as designed. Candidates who score below 60% in Week 1 are offboarded immediately — no wasted Week 2-4 compute. Showed this clearly in demo.

## One Fail
APScheduler fires the pipeline in a background thread inside Streamlit, which can cause SQLite threading issues on Windows. Fixed by adding `check_same_thread=False` to SQLite connection and using a single scheduler instance.
