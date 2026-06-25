"""
L&D Team Supervisor.
LLM-driven orchestrator for the 4-week training programme.
Tracks cohort health, makes early offboard decisions, reports to Root.
"""

import json
from core.state import PipelineState
from core.llm import ld_evaluate_week, ld_generate_report
from database.db import log_supervisor_decision
from agents.onboarding import run_onboarding
from agents.coach import run_coach
from agents.quiz import run_quiz
from agents.decision import run_decision
from config import TOTAL_WEEKS, EARLY_OFFBOARD_THRESHOLD


def _summarise_week_results(candidates: list, week: int) -> str:
    if not candidates:
        return "No trainees."
    lines = []
    for c in candidates:
        last_quiz = c.get("last_quiz", {})
        score = last_quiz.get("overall_score", 0)
        weak = last_quiz.get("weak_topics", [])
        lines.append(
            f"- {c.get('name')} | {c.get('role')} | "
            f"Week {week} score: {score:.1f}% | "
            f"Weak topics: {', '.join(weak) if weak else 'none'}"
        )
    return "\n".join(lines)


def _summarise_final(ppo: list, pool: list, offboarded: list) -> str:
    return (
        f"PPO ({len(ppo)}): {', '.join(c.get('name', '') for c in ppo)}\n"
        f"Talent Pool ({len(pool)}): {', '.join(c.get('name', '') for c in pool)}\n"
        f"Offboarded ({len(offboarded)}): {', '.join(c.get('name', '') for c in offboarded)}\n"
        f"Avg Alpha v2: {sum(c.get('alpha_v2', 0) for c in ppo + pool + offboarded) / max(len(ppo + pool + offboarded), 1):.1f}"
    )


def run_ld_supervisor(state: PipelineState) -> PipelineState:
    """
    LLM-driven L&D Team Supervisor.
    Manages 4-week training, evaluates cohort weekly, makes final decisions.
    """
    run_id = state.get("run_id", 0)
    ld_instructions = state.get("ld_instructions", "Develop and evaluate this cohort rigorously.")
    reasoning_log = []
    all_early_offboarded = []

    accepted = state.get("accepted_candidates", [])
    if not accepted:
        print("[L&D Supervisor] No candidates to train — skipping")
        return {
            **state,
            "ld_report": {
                "from_supervisor": "ld",
                "to_supervisor": "root",
                "status": "skipped",
                "summary": "No candidates accepted offers.",
                "candidates": [],
                "metadata": {}
            }
        }

    print(f"\n[L&D Supervisor] ▶ Starting L&D for {len(accepted)} trainees")
    log_supervisor_decision(run_id, "ld_supervisor", "started",
                            f"Starting L&D with {len(accepted)} trainees", {})

    # ── STEP 1: Onboard ──────────────────────────────────────────────────────
    print("[L&D Supervisor] → Dispatching Onboarding Agent")
    state = run_onboarding(state)
    onboarded = state.get("onboarded_candidates", [])
    print(f"[L&D Supervisor] {len(onboarded)} trainees onboarded")

    # Set initial state for week loop
    state = {**state, "current_trainees": onboarded, "current_week": 1}
    active_trainees = onboarded[:]

    # ── STEP 2: 4-week training loop ─────────────────────────────────────────
    from database.db import get_quiz_scores

    for week in range(1, TOTAL_WEEKS + 1):
        if not active_trainees:
            print(f"[L&D Supervisor] No active trainees remaining at Week {week}")
            break

        print(f"\n[L&D Supervisor] ── Week {week} ──────────────────────────")

        # Some trainees may have already completed this week elsewhere (e.g.
        # the candidate portal's instant onboarding flow runs Week 1 coach +
        # quiz synchronously on offer acceptance). Re-running coach/quiz for
        # them here would create duplicate quiz_scores rows for the same
        # week+topic. Split them out and only process trainees who genuinely
        # haven't done this week yet.
        to_process = []
        already_done = []
        for t in active_trainees:
            existing_weeks = {q["week"] for q in get_quiz_scores(t["candidate_id"])}
            if week in existing_weeks:
                already_done.append(t)
            else:
                to_process.append(t)

        if already_done:
            print(f"[L&D Supervisor] {len(already_done)} trainee(s) already completed "
                  f"Week {week} — skipping re-run for them")

        if not to_process:
            print(f"[L&D Supervisor] No trainees pending Week {week} coaching/quiz")
            active_trainees = already_done
            continue

        state = {**state, "current_trainees": to_process, "current_week": week}

        # Deliver coaching module
        print(f"[L&D Supervisor] → Coach Agent: Week {week} modules")
        state = run_coach(state)

        # Administer quiz
        print(f"[L&D Supervisor] → Quiz Agent: Week {week} assessment")
        state = run_quiz(state)

        # Evaluate week results with LLM
        week_summary = _summarise_week_results(state.get("coached_candidates", []), week)
        week_eval = ld_evaluate_week(week, week_summary)
        reasoning_log.append(f"WEEK {week} EVAL: {week_eval.get('reasoning', '')}")

        log_supervisor_decision(run_id, "ld_supervisor", f"week_{week}_evaluated",
                                week_eval.get("reasoning", ""), week_eval)

        print(f"[L&D Supervisor] Week {week} cohort avg: {week_eval.get('cohort_avg_score', 0):.1f}% | "
              f"Health: {week_eval.get('cohort_health')}")

        # Surface alert to Root if cohort at risk
        if week_eval.get("root_alert"):
            state = {
                **state,
                "root_reasoning": state.get("root_reasoning", []) + [
                    f"L&D ALERT Week {week}: {week_eval.get('root_alert')}"
                ]
            }

        # Handle early offboards identified by LLM supervisor
        early_offboard_ids = week_eval.get("early_offboard_ids", [])
        week_early_offboarded = state.get("early_offboarded", [])
        all_early_offboarded.extend(week_early_offboarded)

        # Additionally offboard any LLM-flagged candidates
        remaining = []
        for c in state.get("quiz_results", []):
            if c["candidate_id"] in early_offboard_ids:
                from database.db import update_candidate_stage, log_action, add_to_blacklist
                update_candidate_stage(c["candidate_id"], "offboarded", "offboarded")
                add_to_blacklist(c.get("email", ""), reason=f"L&D Supervisor offboard at Week {week}")
                log_action(c["candidate_id"], f"ld_week_{week}", "supervisor_offboard",
                           f"L&D Supervisor flagged for offboarding: {week_eval.get('reasoning', '')}")
                print(f"[L&D Supervisor] {c['name']} offboarded by supervisor decision (Week {week})")
                all_early_offboarded.append({
                    **c,
                    "final_decision": "Offboard",
                    "reason": f"L&D Supervisor decision at Week {week}"
                })
            else:
                remaining.append(c)

        active_trainees = remaining + already_done
        state = {
            **state,
            "early_offboarded": all_early_offboarded,
            "quiz_results": active_trainees,
            "ld_coaching_focus": week_eval.get(f"coaching_focus_week_{week + 1}", "")
        }

    # ── STEP 3: Final decisions ───────────────────────────────────────────────
    print(f"\n[L&D Supervisor] → Decision Agent: Final evaluations")
    state = {**state, "early_offboarded": all_early_offboarded}
    state = run_decision(state)

    ppo = state.get("ppo_candidates", [])
    pool = state.get("talent_pool_candidates", [])
    offboarded = state.get("offboarded_candidates", [])

    # ── STEP 4: Generate report for Root ─────────────────────────────────────
    outcomes_summary = _summarise_final(ppo, pool, offboarded)
    final_report = ld_generate_report(outcomes_summary)
    reasoning_log.append(f"FINAL REPORT: {json.dumps(final_report)}")

    log_supervisor_decision(run_id, "ld_supervisor", "complete",
                            outcomes_summary, final_report)

    print(f"\n[L&D Supervisor] ✓ Complete | PPO: {len(ppo)} | "
          f"Talent Pool: {len(pool)} | Offboarded: {len(offboarded)}")

    return {
        **state,
        "ld_report": {
            "from_supervisor": "ld",
            "to_supervisor": "root",
            "status": "complete",
            "summary": outcomes_summary,
            "candidates": ppo + pool + offboarded,
            "metadata": {"reasoning": reasoning_log, "report": final_report}
        },
        "ld_reasoning": reasoning_log
    }