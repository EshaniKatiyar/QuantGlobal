"""
Scheduler Agent.
Auto-generates interview slots and notifies TL.
"""

import random
from datetime import datetime, timedelta
from database.db import update_candidate_stage, log_action, mark_tl_pending

SLOTS = [
    "Monday 10:00 AM", "Monday 2:00 PM", "Monday 4:00 PM",
    "Tuesday 11:00 AM", "Tuesday 3:00 PM",
    "Wednesday 10:00 AM", "Wednesday 2:00 PM",
    "Thursday 11:00 AM", "Thursday 4:00 PM",
    "Friday 10:00 AM", "Friday 12:00 PM"
]


def run_scheduler(state: dict) -> dict:
    passed = state.get("passed_assessment", [])
    scheduled = []

    for candidate in passed:
        candidate_id = candidate["candidate_id"]
        name = candidate["name"]
        role = candidate["role"]

        slot = random.choice(SLOTS)
        interview_date = (datetime.now() + timedelta(days=random.randint(2, 7))).strftime("%d %b %Y")

        interview = {
            "slot": slot,
            "date": interview_date,
            "format": "Google Meet / Delhi NCR Office",
            "interviewer": "Hiring TL — QuantGlobal",
            "duration": "45 minutes",
            "topics": f"Deep-dive on {role} skills + culture fit"
        }

        update_candidate_stage(candidate_id, "scheduled")
        mark_tl_pending(candidate_id)
        log_action(candidate_id, "scheduling", "interview_scheduled",
                   f"Slot: {slot} | Date: {interview_date} | Format: {interview['format']}")

        print(f"[Scheduler] {name} → {slot} on {interview_date}")
        scheduled.append({**candidate, "interview": interview, "tl_decision": None})

    return {**state, "scheduled_candidates": scheduled, "stage": "tl_approval"}