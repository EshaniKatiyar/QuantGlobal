# WEEK 4 — QuantGlobal L&D Module + Full Integration

## Platform
LangGraph + Cerebras (continued from Week 3)

## Agent Roles

### L&D Team Supervisor
LLM-driven orchestrator for the 4-week training programme. Evaluates cohort health after each week via Cerebras (ld_evaluate_week). Can flag individual candidates for early offboard based on LLM reasoning, independently of the Week 1 score checkpoint. Surfaces root_alert to Root Supervisor if cohort is at risk. Generates final structured report for Root (ld_generate_report). Skips weeks already completed by a trainee to prevent duplicate quiz_scores rows.

### Onboarding Agent
- Creates candidate record in SQLite
- Encrypts PII with AES-256 (Fernet) — key persisted to `.encryption_key` or `.env`, never regenerated per call
- Captures explicit consent before storing any data: "I consent to QuantGlobal processing my personal data for recruitment, assessments, and training purposes." Consent timestamp stored in SQLite
- Generates Streamlit trainee credentials (bcrypt-hashed passwords, never printed to logs)
- Idempotent: skips credential regeneration for candidates already onboarded, reconstructs weekly_scores from DB

### Coach/Trainer Agent
- Cerebras generates personalised weekly training modules per candidate (generate_coaching_module)
- Content is role-branched (Quant Researcher / Algo Trader) and adapts to weak topics and previous week score
- Not a static module library — content is fresh and personalised per trainee per week

### Quiz Agent
- Cerebras generates fresh, role-branched, weak-topic-weighted quiz each week (generate_quiz_questions) — not a hardcoded bank
- Topics scoring <60% in week N are weighted 60% heavier in week N+1 (adaptive weighting)
- Cerebras plays the candidate to answer; separate Cerebras call evaluates — never self-graded
- Week 1 early offboard checkpoint: score <60% → immediate offboard + blacklist, no Week 2–4 cost
- Stage transitions: weeks 1–3 → `coach_week_{N+1}`; week 4 → `awaiting_decision`

### Decision Agent
- Fetches candidates at `awaiting_decision` stage from SQLite
- Reconstructs weekly scores from DB (one avg per week, in order)
- Computes Alpha Score v2 using trajectory-aware learning velocity (PDF §8): improving trend scores higher, not flat average
- LLM (Cerebras) confirms decision and provides reasoning — threshold rule is authoritative
- Three-way decision: Alpha v2 ≥70 → PPO; 50–69 → Talent Pool (re-engage in 6 months); <50 → Offboard + Blacklist
- Populates `ppo_candidates`, `talent_pool_candidates`, `offboarded_candidates` lists for Root and dashboards
- Calls `add_to_blacklist` on offboard, `add_to_talent_pool` on pool

## Alpha Score v2 (0–100)
| Factor | Weight | Signal |
|---|---|---|
| Alpha Score v1 | 75 pts | Carried forward from screening |
| L&D Learning Velocity | 25 pts | Trajectory across 4 weeks — improving trend scores higher |

Decisions: PPO ≥70 | Talent Pool 50–69 | Offboard + Blacklist <50

## Early Offboarding Checkpoint (§6)
| Checkpoint | Trigger | Action | Outcome |
|---|---|---|---|
| Week 1 | Quiz score <60% | Decision Agent fires immediately | Offboard + Blacklist. No Week 2–4 cost. |
| Week 4 (Final) | L&D complete | Alpha Score v2 computed | PPO / Talent Pool / Offboard |

## Feedback & Continuous Improvement Loops (§12)
**Loop 1 — Sourcing yield:** `source_stats` table tracks sourced count and screening pass count per source (GitHub/Google). `get_source_ranking()` returns yield rate per source. Sourcer queries higher-yield source harder on next run. Visible on HR dashboard.

**Loop 2 — Alpha Score calibration:** After each cohort's L&D, Root Supervisor compares top-quartile Alpha v1 scorers' average Alpha v2 against cohort average. If top screeners are not outperforming the cohort post-L&D, `HIGH_DRIFT` flag raised to `calibration_checks` table and surfaced on TL dashboard for manual weight review.

**Loop 3 — Quiz topic trends:** `get_cohort_topic_trends()` surfaces per-topic average scores across all trainees. Consistently low topics signal a Coach/Trainer content gap. Visible on HR dashboard as a heatmap (trainee × topic × score).

## Role-Based Access (§10)
| Role | Permissions | Dashboard View |
|---|---|---|
| TL | View all candidates, approve/reject hire | Alpha Scores, pipeline stage, Hiring Velocity, Supervisor reasoning log, approve button, calibration flags |
| HR | Trigger pipeline, view all stages + logs | Full lifecycle, agent action log, stage filter, supervisor decision log, quiz heatmap, candidate timeline/Gantt |
| Trainee | Own progress only | Weekly modules, quiz scores per topic, Alpha v2, final decision + feedback |
| Candidate | Offer portal | Offer letter, consent checkbox, Accept/Decline, document upload |

## Privacy & Data Security (§11)
- Explicit consent captured before any data stored (consent_timestamp in SQLite)
- AES-256 (Fernet) encryption for all PII documents; key persisted, never regenerated
- bcrypt for all login credentials; raw passwords never logged
- Blacklist: SHA-256 hashed email + phone only — no raw PII stored
- Data retention: failed screening/assessment → PII anonymised within 15 days; offboarded → within 60 days; PPO → retained; blacklisted → hashed identifier only, indefinite

## Hiring Velocity Metric (§14)
Displayed on TL dashboard. Computed as: average stage duration (from `stage_durations` table, populated by `update_candidate_stage` on every stage transition) × remaining stages per active candidate = estimated days to next hire. Real durations, not decorative estimates.

## Candidate Lifecycle Visualisations (HR Dashboard)
- **Quiz Performance Heatmap**: trainee × topic × avg score, `RdYlGn` colour scale via `plotly.express.imshow`
- **Candidate Timeline/Gantt**: horizontal bar per candidate per stage, coloured by stage, via `plotly.express.timeline`. Durations sourced from `stage_timeline` table populated on every real stage transition.

## Autonomous Pipeline (§9)
APScheduler fires pipeline every Monday at 9:00 AM with zero human input. Manual trigger button on HR dashboard as backup. One trigger runs the full lifecycle: source → screen → assess → schedule → (TL approval — only human touchpoint) → offer → onboard → 4-week L&D → PPO/Talent Pool/Offboard. All stages autonomous after trigger except TL hire decision.

## Operational Constraints Met (§15)
| Component | Cost |
|---|---|
| Cerebras Inference API | Free tier |
| GitHub API | Free |
| Google Custom Search API | Free (100 queries/day) |
| Piston API | Free, open source |
| APScheduler | Free, open source |
| LangGraph | Open source |
| Streamlit | Free |
| SQLite + cryptography (AES-256) | Free |
| ngrok | Free tier |

## Deployment
Local + ngrok tunnel (as permitted by brief §16). SQLite DB persists locally; ngrok exposes port 8501 for evaluator access. No ephemeral filesystem issues.

## What I Would Improve With More Time
- Real email integration via SendGrid free tier for offer letters and scheduling confirmations
- Live Google Calendar API integration replacing mock scheduling
- Expanded sourcing to include Naukri API and college placement cell portals for IIT/ISI/CMI
- Alpha Score weight backtesting across multiple cohorts to improve predictive accuracy
- Slack integration for TL notifications at key pipeline milestones
- Multi-cohort analytics — track talent quality trends across hiring batches over time
- Expand to Quant Developer and Risk Quant roles in v2

## One Win
The Week 1 early offboard checkpoint and L&D Supervisor's weekly cohort health evaluation work as designed — underperformers are caught and offboarded without waiting for Week 4, saving training compute and directly implementing QuantGlobal's "hire fast, fire fast" principle.

## One Fail
APScheduler fires the pipeline in a background thread inside Streamlit on Windows, which caused SQLite threading errors (`check_same_thread`). Fixed by passing `check_same_thread=False` in the SQLite connection and using a single persistent scheduler instance guarded by `_scheduler.running` check.