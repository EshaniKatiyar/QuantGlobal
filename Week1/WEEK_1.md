# WEEK_1 — AlphaHire (AI Quant Recruitment Engine)
**Platform:** CrewAI + LM Studio (llama-3.2-3b-instruct) + Streamlit + Ngrok

## Agent Roster
| # | Agent | Role | max_iter |
|---|---|---|---|
| 1 | JD Writer | Generates quant role JD | 2 |
| 2 | Screener | Scores & ranks 5 candidates 0-100 | 2 |
| 3 | Scheduler | Books interview slots for top candidates | 2 |
| 4 | Onboarding Agent | Builds 30-day quant onboarding plan | 2 |
| 5 | Assessment Designer | Writes 3 quant aptitude questions | 2 |

## Prompts (Condensed)
- **JD Writer:** "Write JD for {role}. Output: Title, Location, 5 bullet requirements."
- **Screener:** "Score {candidates} vs {role}. Output: Rank table with Score/100 + SHORTLIST/REJECT."
- **Scheduler:** "Top shortlisted → assign Mon 10AM slots, 1hr apart. Output: table."
- **Onboarding:** "30-day plan for #1 candidate. Output: 3 phases × 3 tasks."
- **Assessor:** "3 quant aptitude Qs. Output: Q, Topic, Answer for each."

## Autonomous Task Demonstrated
> Full pipeline: 5 candidates ingested → JD generated → scored → interviews
> scheduled → onboarding plan created → aptitude test designed.
> Zero human input after trigger.

## WIN
> All 5 agents completed sequentially on llama-3.2-3b-instruct via LM Studio.
> Full dossier generated and saved to outputs/ autonomously.

## FAIL / LESSON
> 3b model repeated onboarding phases 3x — fixed with deduplication in app.py.
> Table formatting required custom parsing due to inconsistent pipe output.
