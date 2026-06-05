from crewai import Task
from agents import jd_writer, screener, scheduler, onboarding, assessor
import json

def build_tasks(data: dict):
    role = data["open_role"]
    candidates_str = json.dumps(data["candidates"], indent=2)
    role_str = json.dumps(role, indent=2)

    t1 = Task(
        description=f"""Write a job description for this role: {role_str}
OUTPUT FORMAT (strictly follow):
Title: [title]
Location: [location]
Requirements:
- [bullet 1]
- [bullet 2]
- [bullet 3]
- [bullet 4]
- [bullet 5]""",
        expected_output="Job description with title, location, and exactly 5 requirement bullets.",
        agent=jd_writer
    )

    t2 = Task(
        description=f"""Score these candidates for the role {role_str}.
Candidates: {candidates_str}
OUTPUT FORMAT (strictly follow):
Rank | ID | Name | Score/100 | Verdict (SHORTLIST/REJECT)
Use only this table format. No extra text.""",
        expected_output="A ranked table of candidates with scores and verdicts.",
        agent=screener,
        context=[t1]
    )

    t3 = Task(
        description="""From the screener's output, take the top 3 SHORTLISTED candidates.
Assign interview slots starting Monday 10 AM, 1 hour apart.
OUTPUT FORMAT:
Candidate | Date | Time | Mode
Use only this table. No extra text.""",
        expected_output="Interview schedule table for top 3 candidates.",
        agent=scheduler,
        context=[t2]
    )

    t4 = Task(
        description="""You are writing a 30-day onboarding plan for a new Quant Researcher hire.
You MUST output EXACTLY this structure, no more, no less:

Phase 1 (Days 1-10): Technical Setup
1. [task]
2. [task]
3. [task]

Phase 2 (Days 11-20): Strategy & Backtesting
1. [task]
2. [task]
3. [task]

Phase 3 (Days 21-30): Live Research & Review
1. [task]
2. [task]
3. [task]

Rules:
- Start immediately with "Phase 1" — no preamble
- Never repeat a phase header
- Never add extra phases
- Replace [task] with one specific quant onboarding task""",
        expected_output="Exactly 3 phases with exactly 3 tasks each. No repetition.",
        agent=onboarding,
        context=[t2]
    )

    t5 = Task(
        description="""Create 3 quant aptitude screening questions.
OUTPUT FORMAT for each:
Q[n]: [question]
Topic: [topic]
Answer: [answer]
---
Keep questions practical. Test Python, stats, or trading logic.""",
        expected_output="3 quant questions with topics and answers.",
        agent=assessor
    )

    return [t1, t2, t3, t4, t5]