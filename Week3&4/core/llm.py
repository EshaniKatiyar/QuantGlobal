"""
Single Cerebras LLM client used across all supervisors and agents.
All prompts live here for auditability and easy tuning.
"""

import json
import re
import time
from typing import List
from cerebras.cloud.sdk import Cerebras
from config import CEREBRAS_API_KEY, CEREBRAS_MODEL

client = Cerebras(api_key=CEREBRAS_API_KEY, timeout=30.0, max_retries=1)


def call_llm(system: str, user: str, max_tokens: int = 1500, json_mode: bool = False, retries: int = 2) -> str:
    """
    Core LLM call. All agents go through this.
    json_mode=True appends JSON instruction and strips markdown fences.
    Retries on empty/None content (common with truncated reasoning-model output).
    """
    if json_mode:
        user += "\n\nRespond ONLY with valid JSON. No markdown, no explanation, no backticks."

    for attempt in range(retries + 1):
        try:
            response = client.chat.completions.create(
                model=CEREBRAS_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user}
                ],
                max_tokens=max_tokens,
                temperature=0.3
            )
            content = response.choices[0].message.content
            if not content:
                print(f"[LLM] Empty content on attempt {attempt + 1}/{retries + 1} — retrying with more tokens")
                max_tokens = int(max_tokens * 1.5)
                continue

            text = content.strip()
            if json_mode:
                text = re.sub(r"```json|```", "", text).strip()
            return text

        except Exception as e:
            err = str(e)
            if "429" in err or "too_many_requests" in err or "queue_exceeded" in err:
                wait = 3 * (attempt + 1)
                print(f"[LLM] Rate limited — waiting {wait}s before retry {attempt + 1}/{retries + 1}")
                time.sleep(wait)
            else:
                print(f"[LLM] Error on attempt {attempt + 1}/{retries + 1}: {e}")

    return "{}" if json_mode else ""


def parse_json(text: str) -> dict:
    """Safe JSON parser with fallback. Tries to salvage truncated JSON
    (common when a long code answer eats the token budget) before giving up."""
    try:
        return json.loads(text)
    except Exception:
        pass

    try:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass

    # Truncated mid-string/object: trim to the last complete "key": "value"
    # pair and close the braces, rather than discarding everything.
    try:
        last_comma = text.rfind('",')
        if last_comma != -1:
            salvage = text[:last_comma + 1] + "}"
            return json.loads(salvage)
    except Exception:
        pass

    return {}


# ─────────────────────────────────────────────
# ROOT SUPERVISOR PROMPTS
# ─────────────────────────────────────────────

ROOT_SYSTEM = """You are the Root Supervisor of QuantGlobal's AI-native recruitment system.
You orchestrate two teams: the Recruitment Team and the L&D Team.
Your job is to make high-level pipeline decisions based on the current state.
You think like a Chief of Staff at a quant trading firm — fast, data-driven, no fluff.
Always return structured JSON decisions."""


def root_decide_next_action(state_summary: str) -> dict:
    """Root supervisor decides what to do next based on pipeline state."""
    result = call_llm(
        system=ROOT_SYSTEM,
        user=f"""Current pipeline state:
{state_summary}

Decide the next action. Return JSON:
{{
  "action": "dispatch_recruitment" | "dispatch_ld" | "retry_sourcing" | "escalate_to_tl" | "complete" | "abort",
  "reasoning": "why you made this decision",
  "instructions": "specific instructions for the team being dispatched",
  "alert": "any TL alert to surface (empty string if none)"
}}""",
        json_mode=True
    )
    return parse_json(result)


def root_evaluate_recruitment_report(report: str) -> dict:
    """Root evaluates recruitment team's report and decides whether to proceed to L&D."""
    result = call_llm(
        system=ROOT_SYSTEM,
        user=f"""Recruitment Team has completed their work and filed this report:
{report}

Evaluate and decide. Return JSON:
{{
  "proceed_to_ld": true | false,
  "reasoning": "why",
  "cohort_quality": "strong" | "acceptable" | "weak",
  "tl_alert": "message for TL dashboard (empty if none)",
  "instructions_for_ld": "what L&D team should focus on given this cohort"
}}""",
        json_mode=True
    )
    return parse_json(result)


def root_evaluate_ld_report(report: str) -> dict:
    """Root evaluates L&D team's final report."""
    result = call_llm(
        system=ROOT_SYSTEM,
        user=f"""L&D Team has completed their work and filed this report:
{report}

Evaluate the final outcomes. Return JSON:
{{
  "pipeline_health": "excellent" | "good" | "poor",
  "reasoning": "analysis of outcomes",
  "recommendations": "what to improve in next hiring cycle",
  "tl_summary": "executive summary for TL (2-3 sentences)"
}}""",
        json_mode=True
    )
    return parse_json(result)


# ─────────────────────────────────────────────
# RECRUITMENT SUPERVISOR PROMPTS
# ─────────────────────────────────────────────

RECRUITMENT_SYSTEM = """You are the Recruitment Team Supervisor at QuantGlobal.
You manage a team of specialist agents: Sourcer, Screener, Assessment, Scheduler, Offer.
You are responsible for filling the pipeline with qualified quant talent from Delhi-NCR.
You make decisions about which candidates proceed, who gets retried, and when to report back to Root.
Think like a sharp quant hiring manager — precision over volume."""


def recruitment_evaluate_sourcing(candidates_summary: str, instructions: str) -> dict:
    """Recruitment supervisor evaluates sourcing results."""
    result = call_llm(
        system=RECRUITMENT_SYSTEM,
        user=f"""Root Supervisor instructions: {instructions}

Sourcer Agent returned these candidates:
{candidates_summary}

Evaluate quality. Return JSON:
{{
  "quality": "strong" | "acceptable" | "weak",
  "proceed": true | false,
  "retry_sourcing": true | false,
  "retry_reason": "why retry if applicable",
  "reasoning": "your evaluation",
  "candidates_to_screen": "all" | "top_only"
}}""",
        json_mode=True
    )
    return parse_json(result)


def recruitment_evaluate_screening(results_summary: str) -> dict:
    """Recruitment supervisor evaluates screening results."""
    result = call_llm(
        system=RECRUITMENT_SYSTEM,
        user=f"""Screener Agent returned these results:
{results_summary}

Evaluate and decide who proceeds to assessment. Return JSON:
{{
  "proceed_count": <number>,
  "reasoning": "your evaluation",
  "threshold_adjustment": "none" | "lower" | "raise",
  "notes_for_assessment": "what assessment agent should focus on"
}}""",
        json_mode=True
    )
    return parse_json(result)


def recruitment_evaluate_assessment(results_summary: str) -> dict:
    """Recruitment supervisor evaluates assessment results."""
    result = call_llm(
        system=RECRUITMENT_SYSTEM,
        user=f"""Assessment Agent returned these results:
{results_summary}

Evaluate quality of candidates who passed. Return JSON:
{{
  "cohort_strength": "strong" | "acceptable" | "weak",
  "reasoning": "your evaluation",
  "scheduling_priority": "fastest_slot" | "standard",
  "notes_for_tl": "what TL should know about this batch"
}}""",
        json_mode=True
    )
    return parse_json(result)


def recruitment_generate_report(pipeline_summary: str) -> dict:
    """Recruitment supervisor generates final report for Root."""
    result = call_llm(
        system=RECRUITMENT_SYSTEM,
        user=f"""Pipeline summary:
{pipeline_summary}

Generate a structured report for the Root Supervisor. Return JSON:
{{
  "status": "complete" | "partial" | "failed",
  "candidates_sourced": <number>,
  "candidates_accepted": <number>,
  "conversion_rate": "<percentage>",
  "biggest_drop_off_stage": "<stage name>",
  "cohort_quality_assessment": "<your assessment>",
  "recommendations": "<what to improve next cycle>"
}}""",
        json_mode=True
    )
    return parse_json(result)


# ─────────────────────────────────────────────
# L&D SUPERVISOR PROMPTS
# ─────────────────────────────────────────────

LD_SYSTEM = """You are the L&D Team Supervisor at QuantGlobal.
You manage: Onboarding, Coach, Quiz, and Decision agents.
You are responsible for developing quant talent over 4 simulated weeks and making final PPO/offboard decisions.
You track cohort health, identify struggling trainees early, and report to Root Supervisor.
Think like a rigorous quant training director — standards matter, but so does development."""


def ld_evaluate_week(week: int, results_summary: str) -> dict:
    """L&D supervisor evaluates weekly quiz results and decides next action."""
    result = call_llm(
        system=LD_SYSTEM,
        user=f"""Week {week} quiz results for all trainees:
{results_summary}

Evaluate cohort health and decide next steps. Return JSON:
{{
  "cohort_avg_score": <number>,
  "cohort_health": "strong" | "acceptable" | "at_risk",
  "early_offboard_ids": [<candidate_ids to offboard immediately>],
  "reasoning": "your evaluation",
  "coaching_focus_week_{week+1}": "what Coach agent should emphasize next week",
  "root_alert": "alert for Root Supervisor (empty string if none)"
}}""",
        json_mode=True
    )
    return parse_json(result)


def ld_generate_report(outcomes_summary: str) -> dict:
    """L&D supervisor generates final report for Root."""
    result = call_llm(
        system=LD_SYSTEM,
        user=f"""Final L&D outcomes:
{outcomes_summary}

Generate report for Root Supervisor. Return JSON:
{{
  "status": "complete",
  "ppo_count": <number>,
  "talent_pool_count": <number>,
  "offboard_count": <number>,
  "avg_final_alpha_score": <number>,
  "cohort_assessment": "<overall assessment>",
  "strongest_candidate": "<name and why>",
  "weakest_area_across_cohort": "<topic that most trainees struggled with>",
  "recommendations": "<improvements for next cohort>"
}}""",
        json_mode=True
    )
    return parse_json(result)


# ─────────────────────────────────────────────
# AGENT-LEVEL PROMPTS
# ─────────────────────────────────────────────

def screen_candidate_profile(name: str, role: str, bio: str, repos: List[str], stars: int) -> dict:
    """Screener agent: LLM reads actual profile and reasons about fit."""
    from typing import List
    result = call_llm(
        system="""You are a senior quant recruiter at QuantGlobal. 
You evaluate candidates for Quant Researcher and Algo Trader roles with extremely high standards.
You look for genuine quantitative depth, not surface-level keywords.""",
        user=f"""Evaluate this candidate for the role of {role}:

Name: {name}
Bio: {bio}
GitHub Repos: {', '.join(repos) if repos else 'None visible'}
Total Stars: {stars}

Score them on three dimensions (each 0-25):
1. GitHub Signal: quality and relevance of their public work
2. Domain Depth: evidence of genuine quant knowledge in their profile
3. Potential Fit: likelihood of thriving in a fast-paced quant firm

Return JSON:
{{
  "github_signal": <0-25>,
  "domain_depth": <0-25>,
  "potential_fit": <0-25>,
  "total_v1_partial": <sum of above>,
  "key_strengths": "<2-3 specific strengths>",
  "red_flags": "<any concerns, empty string if none>",
  "recommendation": "proceed" | "reject",
  "reasoning": "<your reasoning in 2 sentences>"
}}""",
        json_mode=True
    )
    return parse_json(result)


def generate_assessment_questions(name: str, role: str, repos: List[str], bio: str) -> dict:
    """Assessment agent: generate personalized questions based on candidate's actual repos."""
    from typing import List
    result = call_llm(
        system="""You are a senior quant at QuantGlobal designing technical assessments.
You create targeted, rigorous questions based on what the candidate has actually worked on.
Questions should reveal genuine understanding, not pattern matching.""",
        user=f"""Generate a personalized technical assessment for:
Name: {name}
Role: {role}
Their repos/work: {', '.join(repos) if repos else 'general quant topics'}
Bio context: {bio}

Create 3 questions — 1 practical coding, 2 domain knowledge.
Tailor them specifically to what this candidate has worked on.

Return JSON:
{{
  "practical": {{
    "question": "<specific coding question>",
    "context": "<why this question for this candidate>",
    "expected_concepts": ["<concept1>", "<concept2>"]
  }},
  "domain_1": {{
    "question": "<domain question 1>",
    "expected_keywords": ["<keyword1>", "<keyword2>"]
  }},
  "domain_2": {{
    "question": "<domain question 2>",
    "expected_keywords": ["<keyword1>", "<keyword2>"]
  }}
}}""",
        json_mode=True,
        max_tokens=1800
    )
    return parse_json(result)


def generate_candidate_answers(name: str, role: str, questions: dict, repos: List[str]) -> dict:
    """Cerebras plays the candidate and generates realistic answers."""
    from typing import List
    result = call_llm(
        system=f"""You are {name}, a {role} candidate being assessed at QuantGlobal.
You have worked on: {', '.join(repos) if repos else 'quantitative finance projects'}.
Answer as a real candidate would — competent but not perfect. Show genuine understanding.""",
        user=f"""Answer these assessment questions:

Practical: {questions.get('practical', {}).get('question', '')}
Domain 1: {questions.get('domain_1', {}).get('question', '')}
Domain 2: {questions.get('domain_2', {}).get('question', '')}

Return JSON:
{{
  "practical_answer": "<your code or solution>",
  "domain_1_answer": "<your answer>",
  "domain_2_answer": "<your answer>"
}}""",
        json_mode=True,
        max_tokens=2500
    )
    return parse_json(result)


def evaluate_answers(role: str, questions: dict, answers: dict) -> dict:
    """Separate LLM call evaluates answers — not self-grading."""
    result = call_llm(
        system="""You are an objective quant assessment evaluator at QuantGlobal.
You evaluate candidate answers fairly. Score each answer out of 100 based on correctness, depth, and clarity.
CRITICAL INSTRUCTION:
Keep your 'strongest_area', 'weakest_area', and 'feedback' extremely concise. 
Maximum 15 words per field. Do not write long paragraphs.""",
        user=f"""Evaluate these answers for a {role} position:

Q1 (Practical): {questions.get('practical', {}).get('question', '')}
A1: {answers.get('practical_answer', '')}
Expected concepts: {questions.get('practical', {}).get('expected_concepts', [])}

Q2 (Domain): {questions.get('domain_1', {}).get('question', '')}
A2: {answers.get('domain_1_answer', '')}
Expected keywords: {questions.get('domain_1', {}).get('expected_keywords', [])}

Q3 (Domain): {questions.get('domain_2', {}).get('question', '')}
A3: {answers.get('domain_2_answer', '')}
Expected keywords: {questions.get('domain_2', {}).get('expected_keywords', [])}

Return JSON:
{{
  "practical_score": <0-100>,
  "domain_1_score": <0-100>,
  "domain_2_score": <0-100>,
  "overall_score": <weighted average 0-100>,
  "feedback": "<specific feedback on performance>",
  "strongest_area": "<what they did well>",
  "weakest_area": "<what needs improvement>"
}}""",
        json_mode=True
    )
    return parse_json(result)


def generate_offer_letter(name: str, role: str, alpha_v1: float, strengths: str) -> str:
    """Offer agent: Cerebras writes a personalized offer letter."""
    return call_llm(
        system="""You are the Head of Talent at QuantGlobal writing a formal offer letter.
Be professional, specific, and reference the candidate's actual strengths.""",
        user=f"""Write a formal offer letter for:
Name: {name}
Role: {role}
Alpha Score v1: {alpha_v1:.1f}/75
Key strengths identified: {strengths}

Include: role, location (Delhi-NCR hybrid), joining timeline (2 weeks),
compensation range ({role} market rate for Delhi NCR quant firms),
L&D programme mention, PPO possibility.
Keep it under 300 words. Professional tone.""",
        max_tokens=500
    )


def generate_coaching_module(name: str, role: str, week: int, weak_topics: List[str], prev_score: float) -> dict:
    """Coach agent: Cerebras generates personalized training content."""
    from typing import List
    result = call_llm(
        system="""Generate a training module title, focus areas, and a brief coach note.
CRITICAL: Keep the 'Coach note' extremely concise (maximum 2 short sentences). 
Do not exceed 50 words for the note.""",
        user=f"""Create Week {week} training module for:
Name: {name}
Role: {role}
Previous week score: {prev_score:.1f}% (0 if week 1)
Weak topics to address: {', '.join(weak_topics) if weak_topics else 'none identified yet'}

Generate focused content. Return JSON:
{{
  "title": "<module title>",
  "focus_areas": ["<area1>", "<area2>"],
  "key_concepts": ["<concept1>", "<concept2>", "<concept3>"],
  "practical_exercise": "<specific exercise for this trainee>",
  "resources": ["<resource1>", "<resource2>"],
  "coach_note": "<personal note to {name} based on their progress>"
}}""",
        json_mode=True
    )
    return parse_json(result)


def generate_quiz_questions(role: str, week: int, weak_topics: List[str]) -> dict:
    """Quiz agent: Cerebras generates fresh questions each week based on weak areas."""
    from typing import List
    focus = f"Focus heavily on: {', '.join(weak_topics)}" if weak_topics else "Cover core topics evenly"
    result = call_llm(
        system="""You are a rigorous quant assessment designer at QuantGlobal.
Generate challenging but fair quiz questions for training evaluation.""",
        user=f"""Generate Week {week} quiz for a {role}.
{focus}

Create 4 questions across different topics. Return JSON:
{{
  "questions": [
    {{
      "topic": "<topic name>",
      "question": "<the question>",
      "options": ["A: <option>", "B: <option>", "C: <option>", "D: <option>"],
      "correct": "A" | "B" | "C" | "D",
      "explanation": "<why this answer>"
    }}
  ]
}}""",
        json_mode=True
    )
    return parse_json(result)


def generate_quiz_answers_and_evaluate(role: str, name: str, questions: List[dict]) -> dict:
    """Cerebras plays candidate taking quiz, then separate call evaluates."""
    from typing import List
    # Step 1: Generate answers as candidate
    q_text = "\n".join([f"Q{i+1}: {q['question']}\nOptions: {', '.join(q['options'])}"
                        for i, q in enumerate(questions)])

    answers_raw = call_llm(
        system=f"You are {name}, a {role} trainee at QuantGlobal. Answer these quiz questions.",
        user=f"{q_text}\n\nReturn JSON: {{\"answers\": [\"A\"|\"B\"|\"C\"|\"D\", ...]}}",
        json_mode=True
    )
    answers = parse_json(answers_raw).get("answers", [])

    # Step 2: Evaluate answers
    correct = 0
    topic_results = {}
    for i, q in enumerate(questions):
        ans = answers[i] if i < len(answers) else "A"
        is_correct = ans.upper().startswith(q.get("correct", "A"))
        if is_correct:
            correct += 1
        topic = q.get("topic", "general")
        topic_results[topic] = topic_results.get(topic, [])
        topic_results[topic].append(100 if is_correct else 0)

    topic_scores = {t: sum(v) / len(v) for t, v in topic_results.items()}
    overall = (correct / len(questions) * 100) if questions else 0

    return {
        "overall_score": round(overall, 1),
        "topic_scores": topic_scores,
        "weak_topics": [t for t, s in topic_scores.items() if s < 60],
        "correct": correct,
        "total": len(questions)
    }


def make_final_decision(name: str, role: str, alpha_v1: float,
                        weekly_scores: List[float], topic_scores: dict) -> dict:
    """Decision agent: LLM reasons about the full candidate profile."""
    from typing import List
    result = call_llm(
        system="""You are the final decision maker for QuantGlobal's talent programme.
You make PPO, Talent Pool, or Offboard decisions based on comprehensive performance data.
You are fair but rigorous — QuantGlobal needs exceptional talent.""",
        user=f"""Make final decision for:
Name: {name}
Role: {role}
Alpha Score v1 (pre-L&D): {alpha_v1:.1f}/75
Weekly L&D scores: {weekly_scores}
Topic performance: {topic_scores}
Score trend: {"improving" if len(weekly_scores) > 1 and weekly_scores[-1] > weekly_scores[0] else "declining or flat"}

Thresholds: PPO ≥ 70 Alpha v2, Talent Pool 50-69, Offboard < 50.
Alpha v2 = v1 scaled to 75 + learning velocity bonus up to 25.

Return JSON:
{{
  "alpha_v2": <0-100>,
  "learning_velocity_score": <0-25>,
  "decision": "PPO" | "Talent Pool" | "Offboard",
  "confidence": "high" | "medium" | "low",
  "reasoning": "<specific reasoning referencing their actual scores>",
  "feedback_for_candidate": "<constructive feedback>"
}}""",
        json_mode=True
    )
    return parse_json(result)