"""
Coach/Trainer Agent.
Cerebras generates personalized weekly training modules per candidate.
Content adapts based on role, weak topics, and previous week score.
"""

from core.llm import generate_coaching_module
from database.db import log_action


def run_coach(state: dict) -> dict:
    trainees = state.get("current_trainees", [])
    week = state.get("current_week", 1)
    coaching_focus = state.get("ld_coaching_focus", "")
    coached = []

    for candidate in trainees:
        candidate_id = candidate["candidate_id"]
        name = candidate["name"]
        role = candidate["role"]
        weak_topics = candidate.get("weak_topics", [])
        weekly_scores = candidate.get("weekly_scores", [])
        prev_score = weekly_scores[-1] if weekly_scores else 0.0

        # If L&D supervisor specified a focus, add it to weak topics
        if coaching_focus and coaching_focus not in weak_topics:
            weak_topics = weak_topics + [coaching_focus]

        print(f"[Coach] Generating Week {week} module for {name} ({role})...")

        module = generate_coaching_module(name, role, week, weak_topics, prev_score)

        log_action(
            candidate_id, f"coach_week_{week}", "module_delivered",
            f"Title: {module.get('title', '')} | "
            f"Focus: {', '.join(module.get('focus_areas', []))} | "
            f"Coach note: {module.get('coach_note', '')[:100]}"
        )

        print(f"[Coach] {name} Week {week}: {module.get('title', 'Module delivered')}")

        coached.append({
            **candidate,
            f"module_week_{week}": module,
            "last_module": module
        })

    return {**state, "coached_candidates": coached}