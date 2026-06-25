# WEEK 3 — QuantGlobal AI-Native Recruitment System

## Company Name
QuantGlobal AI Recruitment & L&D System

## Platform
LangGraph + Cerebras (llama3.1-8b / gpt-oss-120b)

## Agent Roles

### Root Supervisor
Orchestrates the full pipeline. Makes LLM-driven decisions on whether to dispatch Recruitment Team, proceed to L&D, retry sourcing, or escalate to TL. Every decision logged with reasoning to supervisor_logs table.

### Recruitment Team Supervisor
LLM-driven orchestrator for the recruitment phase. Dispatches Sourcer → Screener → Assessment → Scheduler → Offer agents in sequence. Evaluates each stage output via Cerebras, retries sourcing if quality is weak, generates structured report for Root Supervisor.

### Sourcer Agent
- Queries GitHub API: `location:Delhi OR Gurgaon OR Noida, language:Python, topic:algorithmic-trading OR topic:quantitative-finance`
- Queries Google Custom Search API: `"quant trader" OR "algorithmic trading" OR "quantitative researcher" Delhi NCR site:github.com`
- Data extracted: username, location, repo names, commit frequency, star count, bio, inferred role
- Checks SQLite blacklist (SHA-256 hashed identifiers) before adding any candidate
- Tags each candidate with inferred role (Quant Researcher / Algo Trader) from repo topics and bio keywords
- Feedback Loop 1: logs sourcing volume and screening yield per source (GitHub vs Google); queries higher-yield source harder on next run
- Minimum output: 5 candidates per run

### Screener Agent
- Computes Alpha Score v1 (0–75): GitHub Signal (0–25) + Background Fit (0–25) + Assessment placeholder (0–25)
- Background Fit tiers: IIT/ISI/CMI = 25, Tier-2 = 15, Other = 5
- Lateral candidates (>2yr exp): work experience score replaces institution tier entirely
- Uses Cerebras to extract institute and years of experience from bio text
- Feedback Loop 1: records which source produced a screening pass

### Assessment Agent
- Role-branched two-round evaluation: practical coding test + domain knowledge round
- Quant Researcher: options pricing, probability, backtesting questions — generated from candidate's actual repos via Cerebras
- Algo Trader: order books, execution algos, risk management — generated from candidate's actual repos via Cerebras
- Cerebras plays the candidate to generate answers; separate Cerebras call evaluates — never self-graded
- All code submissions run via Piston API sandbox (timeout: 5s, memory: 256MB, no network access) — exec()/eval() never used on QuantGlobal infrastructure
- Assessment score feeds Alpha Score v1 finalisation

### Scheduler Agent
- Auto-generates mock interview slot and date
- Records TL pending timestamp (24h timeout window per §13)
- TL notified via dashboard — single binary Approve/Reject

### Offer Agent
- Generates personalised offer letter via Cerebras on TL approval only — never auto-generated without real TL decision on file
- Generates Candidate Portal credentials (username = email prefix, bcrypt-hashed password)
- Candidate accepts via portal (real human action) — supervisor never decides on candidate's behalf

## LLM Prompts Used (all in core/llm.py)
- `root_decide_next_action` — pipeline decision making
- `recruitment_evaluate_sourcing` — quality assessment of sourced batch
- `recruitment_evaluate_screening` — screening results evaluation
- `recruitment_evaluate_assessment` — cohort strength assessment
- `screen_candidate_profile` — per-candidate GitHub/bio reasoning (Screener)
- `generate_assessment_questions` — personalised from candidate's repos
- `generate_candidate_answers` — Cerebras plays candidate
- `evaluate_answers` — separate evaluator (not self-grading)
- `generate_offer_letter` — personalised offer text

## Alpha Score v1 (0–75)
| Factor | Weight | Fresher | Lateral (>2yr exp) |
|---|---|---|---|
| GitHub Signal | 25 pts | Repo quality, commit consistency, quant topic relevance | Same |
| Background Fit | 25 pts | IIT/ISI/CMI=25, Tier-2=15, Other=5 | Work experience score (0–25) replaces institute entirely |
| Assessment Score | 25 pts | Speed + accuracy, role-branched | Same |

## TL Bottleneck Design (§13)
- TL sees fully pre-evaluated candidate: Alpha Score, assessment results, scheduled slot
- Single binary decision: Approve or Reject via dashboard button
- No TL response within 24h → candidate flagged pending on dashboard; pipeline continues for others in parallel
- Supervisor never auto-approves or auto-rejects

## Tech Stack
LangGraph, Cerebras API (free), GitHub API (free), Google Custom Search API (free, 100/day), Piston API (free), Streamlit, SQLite, APScheduler, bcrypt, cryptography (Fernet AES-256), ngrok

## One Win
LLM-driven Recruitment Supervisor correctly retried sourcing when first batch quality was flagged as weak, and surfaced a TL alert when 0% of candidates passed assessment — behaviour a rule-based system would not produce.

## One Fail
Google Custom Search API returned 403 errors during development due to API key restrictions. Resolved by verifying Custom Search API was enabled on the correct GCP project. Switched to a representative mock pool as fallback when real APIs return no Delhi-NCR results.