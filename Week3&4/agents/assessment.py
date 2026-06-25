"""
Assessment Agent.
Generates personalized questions from candidate's actual repos using Cerebras.
Cerebras plays candidate to generate answers.
Separate Cerebras call evaluates answers — not self-grading.
Code submissions run via isolated sandbox.
"""

from core.llm import (
    generate_assessment_questions,
    generate_candidate_answers,
    evaluate_answers
)
from core.tools import execute_code_safely
from utils.alpha_score import compute_alpha_v1
from database.db import update_candidate_stage, update_alpha_score, log_action, save_candidate_code

PASS_THRESHOLD = 55  # overall score out of 100


def assess_single(candidate: dict) -> dict:
    candidate_id = candidate["candidate_id"]
    name = candidate["name"]
    role = candidate["role"]
    repos = candidate.get("repos", [])
    bio = candidate.get("bio", "")

    print(f"[Assessment] Generating personalized questions for {name} ({role})...")

    # Step 1: Generate personalized questions from their actual repos
    questions = generate_assessment_questions(name, role, repos, bio)
    if not questions:
        print(f"[Assessment] Failed to generate questions for {name} — rejecting")
        update_candidate_stage(candidate_id, "assessment", "rejected")
        log_action(candidate_id, "assessment", "question_generation_failed",
                   "Could not generate personalized questions")
        return {**candidate, "assessment_passed": False, "assessment_score": 0}

    log_action(candidate_id, "assessment", "questions_generated",
               f"Practical: {questions.get('practical', {}).get('question', '')[:100]}")

    # Step 2: Cerebras plays candidate and generates answers
    print(f"[Assessment] Generating candidate answers for {name}...")
    answers = generate_candidate_answers(name, role, questions, repos)
    if not answers:
        print(f"[Assessment] Candidate answers came back empty for {name} — retrying once")
        answers = generate_candidate_answers(name, role, questions, repos)

    # Step 2b: If practical answer contains code, run it in isolated sandbox
    practical_answer = answers.get("practical_answer", "")
    piston_result = None
    if "def " in practical_answer or "import " in practical_answer:
        print(f"[Assessment] Running {name}'s code in isolated sandbox...")
        piston_result = execute_code_safely(practical_answer)
        log_action(candidate_id, "assessment", "code_sandboxed",
                   f"Sandbox output: {piston_result.get('stdout', '')[:100]} | "
                   f"Success: {piston_result.get('success')}")

    # Step 3: Separate LLM call evaluates answers (not self-grading)
    print(f"[Assessment] Evaluating {name}'s answers...")
    evaluation = evaluate_answers(role, questions, answers)
    if not evaluation:  # empty dict = LLM/parse failure, not a real 0 score
        print(f"[Assessment] Evaluation came back empty for {name} — retrying once")
        evaluation = evaluate_answers(role, questions, answers)

    overall_score = float(evaluation.get("overall_score", 0.0))
    passed = overall_score >= PASS_THRESHOLD

    # Recompute Alpha v1 with real assessment score (scaled to 25)
    assessment_component = (overall_score / 100) * 25
    alpha_v1 = compute_alpha_v1(
        candidate.get("github_signal", 10),
        candidate.get("background_fit", 10),
        assessment_component
    )

    update_alpha_score(candidate_id, v1=alpha_v1)
    update_candidate_stage(candidate_id, "assessment", "active" if passed else "rejected")

    log_action(
        candidate_id, "assessment", "assessment_complete",
        f"Overall: {overall_score:.1f}/100 | Alpha v1 final: {alpha_v1:.1f}/75 | "
        f"Passed: {passed} | Strongest: {evaluation.get('strongest_area', '')} | "
        f"Weakest: {evaluation.get('weakest_area', '')} | "
        f"Feedback: {evaluation.get('feedback', '')}"  # <-- Removed the [:100] slice!
    )

    print(f"[Assessment] {name} — Score: {overall_score:.1f}/100 | "
          f"Alpha v1: {alpha_v1:.1f}/75 | {'PASS' if passed else 'REJECT'}")
# Save the raw code to the database for the HR Dashboard!
    save_candidate_code(candidate_id, questions, answers)

    return {
        **candidate,
        "alpha_v1": alpha_v1,
        "assessment_score": overall_score,
        "assessment_questions": questions,
        "assessment_answers": answers,
        "assessment_evaluation": evaluation,
        "piston_result": piston_result,
        "assessment_passed": passed,
        "assessment_feedback": evaluation.get("feedback", ""),
        "strongest_area": evaluation.get("strongest_area", ""),
        "weakest_area": evaluation.get("weakest_area", "")
    }


def run_assessment(state: dict) -> dict:
    passed_screening = state.get("passed_screening", [])
    assessed = []
    passed = []

    for candidate in passed_screening:
        result = assess_single(candidate)
        assessed.append(result)
        if result.get("assessment_passed"):
            passed.append(result)

    print(f"[Assessment] {len(passed)}/{len(passed_screening)} passed assessment")

    return {
        **state,
        "assessed_candidates": assessed,
        "passed_assessment": passed,
        "stage": "scheduling"
    }