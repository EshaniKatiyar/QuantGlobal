"""
Decision Agent.
Computes Alpha Score v2 using trajectory-aware learning velocity (PDF §8),
then LLM reasons over the full profile to make PPO / Talent Pool / Offboard.
Populates ppo_candidates / talent_pool_candidates / offboarded_candidates
so L&D supervisor, Root, and dashboards all read correct outcomes.
"""

import json
from core.llm import call_llm
from utils.alpha_score import compute_alpha_v2, get_decision
from database.db import (
    get_candidates_by_stage, get_quiz_scores,
    update_candidate_stage, update_alpha_v2, log_action,
    add_to_blacklist, add_to_talent_pool
)


def run_decision(state: dict) -> dict:
    # Candidates promoted to final stage by the Week 4 quiz transition
    candidates_to_evaluate = get_candidates_by_stage("awaiting_decision")

    ppo = []
    talent_pool = []
    offboarded = list(state.get("early_offboarded", []))  # carry early offboards forward

    if not candidates_to_evaluate:
        print("[Decision] No candidates currently awaiting final evaluation.")
        return {
            **state,
            "ppo_candidates": ppo,
            "talent_pool_candidates": talent_pool,
            "offboarded_candidates": offboarded,
            "stage": "complete"
        }

    for c in candidates_to_evaluate:
        candidate_id = c["id"]
        name = c["name"]
        role = c.get("role", "Quant Researcher")
        email = c.get("email", "")
        alpha_v1 = float(c.get("alpha_score_v1") or 40.0)

        # Reconstruct weekly scores from DB (one avg per week, in week order)
        quizzes = get_quiz_scores(candidate_id)
        weeks = sorted(set(q["week"] for q in quizzes))
        weekly_scores = []
        for w in weeks:
            w_scores = [q["score"] for q in quizzes if q["week"] == w]
            weekly_scores.append(sum(w_scores) / len(w_scores))

        # Trajectory-aware Alpha v2 (PDF §8: improving trend scores higher)
        alpha_v2 = compute_alpha_v2(alpha_v1, weekly_scores)
        rule_decision = get_decision(alpha_v2)  # PPO / Talent Pool / Offboard

        print(f"[Decision] {name} | Alpha v1: {alpha_v1:.1f} | "
              f"Weekly: {[round(s,1) for s in weekly_scores]} | "
              f"Alpha v2: {alpha_v2:.1f} → {rule_decision}")

        # LLM reasons over the profile but the threshold rule is authoritative
        prompt = f"""You are the Final Decision Agent for QuantGlobal.
Candidate '{name}' ({role}) finished 4 weeks of L&D.

LOCKED METRICS (do not recalculate):
- Alpha v1: {alpha_v1:.1f}/75
- Weekly scores: {weekly_scores}
- Final Alpha v2: {alpha_v2:.1f}/100
- Rule outcome: {rule_decision}

Confirm the decision and give a one-line reasoning referencing the trajectory.
Return JSON: {{"decision": "{rule_decision}", "reasoning": "<one line>"}}"""

        response = call_llm(system="You are the final L&D evaluator.",
                            user=prompt, json_mode=True)
        try:
            parsed = json.loads(response) if isinstance(response, str) else response
        except Exception:
            parsed = {}
        reasoning = parsed.get("reasoning", f"Alpha v2 {alpha_v2:.1f} → {rule_decision}")

        # Persist Alpha v2
        update_alpha_v2(candidate_id, alpha_v2)

        record = {**c, "candidate_id": candidate_id, "alpha_v1": alpha_v1,
                  "alpha_v2": alpha_v2, "decision_reasoning": reasoning}

        # Map rule decision → stage + side effects
        if rule_decision == "PPO":
            update_candidate_stage(candidate_id, "ppo", "ppo")
            log_action(candidate_id, "decision", "ppo_awarded",
                       f"Alpha v2: {alpha_v2:.1f} | {reasoning}")
            print(f"[Decision] {name} → 🏆 PPO | Alpha v2: {alpha_v2:.1f}")
            ppo.append({**record, "final_decision": "PPO"})

        elif rule_decision == "Talent Pool":
            update_candidate_stage(candidate_id, "talent_pool", "talent_pool")
            add_to_talent_pool(candidate_id, alpha_v2)
            log_action(candidate_id, "decision", "talent_pool",
                       f"Alpha v2: {alpha_v2:.1f} | {reasoning}")
            print(f"[Decision] {name} → 🔁 Talent Pool | Alpha v2: {alpha_v2:.1f}")
            talent_pool.append({**record, "final_decision": "Talent Pool"})

        else:  # Offboard
            update_candidate_stage(candidate_id, "offboarded", "offboarded")
            add_to_blacklist(email, reason=f"Below threshold after L&D. Alpha v2: {alpha_v2:.1f}")
            log_action(candidate_id, "decision", "offboarded",
                       f"Alpha v2: {alpha_v2:.1f} | {reasoning}")
            print(f"[Decision] {name} → 🚪 Offboard | Alpha v2: {alpha_v2:.1f}")
            offboarded.append({**record, "final_decision": "Offboard"})

    return {
        **state,
        "ppo_candidates": ppo,
        "talent_pool_candidates": talent_pool,
        "offboarded_candidates": offboarded,
        "stage": "complete"
    }