# WEEK 3 — QuantGlobal AI Recruitment System

## Company Name
QuantGlobal AI Recruitment & L&D System

## Platform
LangGraph (stateful, hierarchical, conditional branching)

## Agent Roles

### Root Supervisor
Orchestrates the full pipeline. Routes candidates from Recruitment phase to L&D phase. Maintains global state. Runs a post-L&D Alpha Score calibration check (Feedback Loop 2).

### Recruitment Team Supervisor
Manages Sourcer, Screener, Assessment, Scheduler, Offer agents. Drives candidates from sourcing to offer acceptance. TL approval and offer acceptance are real human decisions (dashboard / candidate portal) — the supervisor only picks up decisions that have already been made, it never simulates or auto-decides them.

### Sourcer Agent
- Queries GitHub API (Delhi/NCR, Python, algo-trading topics)
- Queries Google Custom Search API
- Checks SQLite blacklist before adding candidates
- Tags each candidate with inferred role (Quant Researcher / Algo Trader)
- **Feedback Loop 1:** tracks each source's screening pass-through rate and queries the higher-yield source harder on subsequent runs

### Screener Agent
- Computes Alpha Score v1 (0-75)
- Factors: GitHub Signal (25) + Background Fit (25) + Assessment Score (25)
- Lateral candidate scoring: work experience replaces institute score for >2yr exp
- Background Fit tiers: IIT/ISI/CMI = 25, Tier-2 = 15, Other = 5 (matches Revised Plan §8)
- Uses the shared Cerebras client (`core/llm.py`) to extract institute/experience from bio text — no duplicate ad-hoc LLM client

### Assessment Agent
- Role-branched practical test + domain knowledge round
- All code runs via Piston API sandbox (never on QuantGlobal infra)
- Quant Researcher: options pricing / stat-arb style questions, generated per-candidate from their actual repos
- Algo Trader: execution / market-microstructure questions, generated per-candidate from their actual repos
- A separate Cerebras call evaluates answers — never self-graded

### Scheduler Agent
- Auto-generates mock interview slot + date
- Starts the TL decision timer (`tl_pending_since`) the moment a candidate is scheduled
- TL notified via dashboard

### Offer Agent
- Generates a personalized offer letter ONLY for candidates with a real, on-record TL approval
- Candidate must accept via the Candidate Portal (real human action, not simulated) before entering L&D

## TL Approval Workflow (Revised Plan §13)
- TL sees a fully pre-evaluated candidate (Alpha Score, assessment results, scheduling slot)
- Single binary decision: Approve or Reject, via dashboard button
- If no decision within `TL_APPROVAL_TIMEOUT_HOURS` (default 24h), the candidate is flagged **pending** on the dashboard — never auto-approved or auto-rejected — while the pipeline continues processing other candidates in parallel
- The Recruitment Supervisor checks for overdue pending candidates at the start of every run

## LLM Prompts Used

### Screener — Institute/Experience Extraction
```
Extract institute name and years of experience from this bio.
Bio: {bio}
Return JSON: {"institute": "<name or 'Other'>", "years_experience": <number>}
```

## One Win
Mock candidate fallback works perfectly — when GitHub/Google APIs don't return enough Delhi/NCR results, the system fills up to 5 candidates automatically without breaking the pipeline.

## One Fail
Google Custom Search API has a 100 queries/day free limit which gets exhausted quickly during testing. Switched to mocking Google results in dev and only using real API for final demo run.
