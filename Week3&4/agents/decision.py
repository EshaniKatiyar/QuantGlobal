"""
Decision Agent.
Cerebras reasons about the full candidate profile and makes PPO/Talent Pool/Offboard decision.
Not just threshold math — LLM considers trajectory, strengths, weaknesses.
"""

from core.llm import make_final_decision
from database.db import (
    update_candidate_stage, update_alpha_score,
    add_to_blacklist, add_to_talent_pool, log_action
)



from core.llm import call_llm
from database.db import update_candidate_stage, log_action, get_quiz_scores, get_candidates_by_stage, update_alpha_v2
import json

def run_decision(state: dict) -> dict:
    
    # ── LOGICALLY PERFECT ──
    # Simply ask the database who has arrived at the final stage. No hacks needed.
    candidates_to_evaluate = get_candidates_by_stage("awaiting_decision")

    evaluated = []

    if not candidates_to_evaluate:
        print("[Decision] No candidates currently waiting for final evaluation.")
        return state

    for c in candidates_to_evaluate:
        candidate_id = c["id"]
        name = c["name"]
        
        # THE FIX: Default Alpha v1 to 40.0 if missing or None
        alpha_v1 = float(c.get("alpha_score_v1") or 40.0)
        
        # 1. Fetch real quiz scores from DB
        quizzes = get_quiz_scores(candidate_id)
        scores = [q["score"] for q in quizzes]
        
        # 2. Deterministic Math (No LLM hallucinations)
        quiz_avg = sum(scores) / len(scores) if scores else 0
        learning_velocity = (quiz_avg / 100) * 25
        alpha_v2 = round(alpha_v1 + learning_velocity, 2)

        print(f"[Decision] Evaluating {name} | Alpha v1: {alpha_v1} | Avg Quiz: {quiz_avg:.1f}%")

        # 3. Force the LLM to use the verified math
        prompt = f"""
You are the Final Decision Agent for QuantGlobal.
The candidate '{name}' has completed 4 weeks of L&D.

HARD METRICS (Do not recalculate these):
- Base Alpha v1: {alpha_v1}/75
- Average Quiz Score: {quiz_avg:.1f}%
- Final Alpha v2: {alpha_v2}/100

RULES:
- If Alpha v2 >= 70: Return "ppo" (Pre-Placement Offer)
- If Alpha v2 between 50-69: Return "talent_pool"
- If Alpha v2 < 50: Return "offboarded"

Return JSON format strictly:
{{
    "decision": "ppo" | "talent_pool" | "offboarded",
    "reasoning": "Brief explanation referencing the locked Alpha v2 score of {alpha_v2}."
}}
"""
        response = call_llm(system="You are the final L&D evaluator.", user=prompt, json_mode=True)
        result = json.loads(response) if isinstance(response, str) else response
        
        decision = result.get("decision", "talent_pool")
        reasoning = result.get("reasoning", "Score evaluated.")
        
        # Update DB
        update_candidate_stage(candidate_id, decision, decision)
        update_alpha_v2(candidate_id, alpha_v2)
        log_action(candidate_id, "decision", decision, f"Alpha v2: {alpha_v2} | Confidence: high | Reasoning: {reasoning}")
        
        print(f"[Decision] {name} → {decision.upper()} | Alpha v2: {alpha_v2}")
        evaluated.append({**c, "alpha_score_v2": alpha_v2, "decision": decision})

    return {**state, "evaluated_trainees": evaluated}