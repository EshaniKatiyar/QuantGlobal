"""
Quiz Agent.
Cerebras generates fresh questions each week based on role and weak topics.
Cerebras plays the candidate to answer.
Separate evaluation scores the answers.
Week 1 early offboard checkpoint enforced here.
"""

from core.llm import generate_quiz_questions, generate_quiz_answers_and_evaluate
from database.db import save_quiz_score, log_action, update_candidate_stage, add_to_blacklist
from config import EARLY_OFFBOARD_THRESHOLD


def quiz_single(candidate: dict, week: int) -> dict:
    candidate_id = candidate["candidate_id"]
    name = candidate["name"]
    role = candidate["role"]
    weak_topics = candidate.get("weak_topics", [])

    print(f"[Quiz] Generating Week {week} quiz for {name} ({role})...")

    # Generate questions (Cerebras, fresh each week, weak-topic weighted)
    quiz_data = generate_quiz_questions(role, week, weak_topics)
    questions = quiz_data.get("questions", [])

    if not questions:
        print(f"[Quiz] Failed to generate questions for {name} — using score 85")
        return {**candidate, "last_quiz": {"overall_score": 85, "topic_scores": {}, "weak_topics": []}}

    # Cerebras plays candidate + evaluate
    result = generate_quiz_answers_and_evaluate(role, name, questions)

    overall_score = result.get("overall_score", 0)
    topic_scores = result.get("topic_scores", {})
    new_weak_topics = result.get("weak_topics", [])

    # Save per-topic scores to DB
    for topic, score in topic_scores.items():
        save_quiz_score(candidate_id, week, topic, score)

    log_action(
        candidate_id, f"quiz_week_{week}", "quiz_completed",
        f"Score: {overall_score:.1f}% | Topics: {topic_scores} | "
        f"Weak: {new_weak_topics} | Correct: {result.get('correct')}/{result.get('total')}"
    )

    print(f"[Quiz] {name} Week {week}: {overall_score:.1f}% | "
          f"Weak topics: {new_weak_topics if new_weak_topics else 'none'}")

    weekly_scores = candidate.get("weekly_scores", []) + [overall_score]

    return {
        **candidate,
        "weekly_scores": weekly_scores,
        "weak_topics": new_weak_topics,
        "last_quiz": {
            "overall_score": overall_score,
            "topic_scores": topic_scores,
            "weak_topics": new_weak_topics
        }
    }


def run_quiz(state: dict) -> dict:
    trainees = state.get("coached_candidates", [])
    week = state.get("current_week", 1)
    results = []
    early_offboarded = []

    for candidate in trainees:
        result = quiz_single(candidate, week)
        score = result.get("last_quiz", {}).get("overall_score", 0)

        # Safely fetch the ID for use in either branch
        candidate_id = candidate.get("candidate_id", candidate.get("id"))

        # Week 1 early offboard checkpoint
        if week == 1 and score < EARLY_OFFBOARD_THRESHOLD:
            print(f"[Quiz] ⚠️  {candidate['name']} scored {score:.1f}% in Week 1 "
                  f"— EARLY OFFBOARD (threshold: {EARLY_OFFBOARD_THRESHOLD}%)")
            update_candidate_stage(candidate_id, "offboarded", "offboarded")
            add_to_blacklist(candidate.get("email", ""),
                             reason=f"Failed Week 1 L&D checkpoint: {score:.1f}%")
            log_action(candidate_id, "quiz_week_1", "early_offboard",
                       f"Score {score:.1f}% below threshold {EARLY_OFFBOARD_THRESHOLD}% — offboarded")
            early_offboarded.append({
                **result,
                "final_decision": "Offboard",
                "reason": f"Week 1 score {score:.1f}% below threshold"
            })
        else:
            # ── THE ONCE-AND-FOR-ALL FIX: Proper State Machine Transitions ──
            if week < 4:
                next_stage = f"coach_week_{week + 1}"
            else:
                next_stage = "awaiting_decision"  # Week 4 is done, ready for PPO!
            
            # Promote the candidate to the next stage organically
            update_candidate_stage(candidate_id, next_stage)
            # ────────────────────────────────────────────────────────────────
            
            results.append(result)

    existing_early = state.get("early_offboarded", [])
    return {
        **state,
        "quiz_results": results,
        "early_offboarded": existing_early + early_offboarded,
        "current_week": week
    }