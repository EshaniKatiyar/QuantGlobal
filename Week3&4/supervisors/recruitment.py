"""
Recruitment Team Supervisor.
LLM-driven orchestrator for the recruitment pipeline.
Dispatches agents, evaluates outputs, makes decisions, reports to Root.

Per Revised Plan §13, the TL approval is the ONLY human touchpoint in the
pipeline: a single binary Approve/Reject via the dashboard, with a
configurable 24h timeout after which the candidate is flagged pending (not
auto-decided) while the pipeline continues for everyone else in parallel.
Offer acceptance is likewise a real human action taken in the Candidate
Portal (app.py) — the supervisor never decides it on the candidate's behalf.
"""

import json
from core.state import PipelineState
from database.db import get_active_candidate_count
from core.llm import (
    recruitment_evaluate_sourcing,
    recruitment_evaluate_screening,
    recruitment_evaluate_assessment,
    recruitment_generate_report
)
from database.db import (
    log_supervisor_decision, get_candidates_by_stage,
    get_overdue_tl_pending, flag_tl_overdue, update_candidate_stage, log_action
)
from agents.sourcer import run_sourcer
from agents.screener import run_screener
from agents.assessment import run_assessment
from agents.scheduler import run_scheduler
from agents.offer import run_offer
from config import TL_APPROVAL_TIMEOUT_HOURS


def _summarise_candidates(candidates: list) -> str:
    if not candidates:
        return "No candidates."
    lines = []
    for c in candidates:
        lines.append(
            f"- {c.get('name')} | {c.get('role')} | "
            f"Source: {c.get('source')} | "
            f"Repos: {len(c.get('repos', []))} | "
            f"Stars: {c.get('stars', 0)} | "
            f"Bio: {c.get('bio', '')[:80]}"
        )
    return "\n".join(lines)


def _summarise_screened(candidates: list) -> str:
    if not candidates:
        return "No candidates passed screening."
    lines = []
    for c in candidates:
        lines.append(
            f"- {c.get('name')} | {c.get('role')} | "
            f"Alpha v1: {c.get('alpha_v1', 0):.1f}/75 | "
            f"Passed: {c.get('screening_passed', False)}"
        )
    return "\n".join(lines)


def _summarise_assessed(candidates: list) -> str:
    if not candidates:
        return "No candidates passed assessment."
    lines = []
    for c in candidates:
        lines.append(
            f"- {c.get('name')} | {c.get('role')} | "
            f"Alpha v1: {c.get('alpha_v1', 0):.1f}/75 | "
            f"Assessment score: {c.get('assessment_score', 0):.1f} | "
            f"Passed: {c.get('assessment_passed', False)}"
        )
    return "\n".join(lines)


def _flag_overdue_tl_pending(run_id: int):
    """§13: candidates past the TL decision window are flagged pending, not
    auto-rejected or auto-approved. They surface on the TL/HR dashboard."""
    overdue = get_overdue_tl_pending(TL_APPROVAL_TIMEOUT_HOURS)
    for c in overdue:
        flag_tl_overdue(c["id"])
        log_action(c["id"], "tl_approval", "tl_decision_overdue",
                   f"No TL decision after {TL_APPROVAL_TIMEOUT_HOURS}h — flagged pending on dashboard")
        print(f"[Recruitment Supervisor] ⏰ {c['name']} overdue for TL decision "
              f"({TL_APPROVAL_TIMEOUT_HOURS}h+) — flagged, pipeline continues for others")
    return overdue


def run_recruitment_supervisor(state: PipelineState) -> PipelineState:
    """
    LLM-driven Recruitment Team Supervisor.
    Orchestrates all recruitment agents and makes pipeline decisions.
    """
    run_id = state.get("run_id", 0)
    instructions = state.get("recruitment_instructions", "Source, screen, assess and onboard qualified quant candidates from Delhi-NCR.")
    reasoning_log = []

    print("\n[Recruitment Supervisor] ▶ Starting recruitment orchestration")
    log_supervisor_decision(run_id, "recruitment_supervisor", "started",
                            "Recruitment supervisor initialised", {})

    # Surface anyone whose TL decision is overdue from a PREVIOUS run before
    # doing anything else this run, per the §13 timeout rule.
    overdue = _flag_overdue_tl_pending(run_id)
    if overdue:
        reasoning_log.append(f"TL TIMEOUT: {len(overdue)} candidate(s) flagged overdue for TL decision")

    # ── STEP 1: Source candidates ────────────────────────────────────────────
    print("[Recruitment Supervisor] → Dispatching Sourcer Agent")
    state = run_sourcer(state)
    sourced = state.get("sourced_candidates", [])

    sourcing_summary = _summarise_candidates(sourced)
    sourcing_eval = recruitment_evaluate_sourcing(sourcing_summary, instructions)
    reasoning_log.append(f"SOURCING EVAL: {sourcing_eval.get('reasoning', '')}")

    log_supervisor_decision(run_id, "recruitment_supervisor", "sourcing_evaluated",
                            sourcing_eval.get("reasoning", ""), sourcing_eval)

    print(f"[Recruitment Supervisor] Sourcing quality: {sourcing_eval.get('quality')} | "
          f"Proceed: {sourcing_eval.get('proceed')}")

    if not sourced:
        active_count = get_active_candidate_count()
        
        # Did we return 0 because the pipeline is full?
        if active_count > 0:
            print(f"[Recruitment Supervisor] Sourcing bypassed. Proceeding to process {active_count} existing candidates.")
            reasoning_log.append("Sourcing bypassed due to active backlog.")
            
            report = {"status": "success", "reason": "Bypassed sourcing to process backlog"}
            log_supervisor_decision(run_id, "recruitment_supervisor", "success", "Bypassed sourcing", report)
            
            return {
                **state,
                "recruitment_report": {
                    "from_supervisor": "recruitment",
                    "to_supervisor": "root",
                    "status": "success", # SUCCESS, NOT FAILED!
                    "summary": f"Sourcing bypassed. Processing {active_count} active candidates in backlog.",
                    "candidates": [],
                    "metadata": {"reasoning": reasoning_log}
                },
                "recruitment_reasoning": reasoning_log
            }
            
        else:
            # True failure: 0 active candidates AND the sourcer found nobody.
            report = {"status": "failed", "reason": "No candidates sourced after retry"}
            log_supervisor_decision(run_id, "recruitment_supervisor", "failed", "No candidates sourced", report)
            
            return {
                **state,
                "recruitment_report": {
                    "from_supervisor": "recruitment",
                    "to_supervisor": "root",
                    "status": "failed",
                    "summary": "Sourcer returned 0 candidates and the pipeline is empty.",
                    "candidates": [],
                    "metadata": {"reasoning": reasoning_log}
                },
                "recruitment_reasoning": reasoning_log
            }

    # ── STEP 2: Screen candidates ─────────────────────────────────────────────
    print(f"[Recruitment Supervisor] → Dispatching Screener Agent ({len(sourced)} candidates)")
    state = run_screener(state)
    passed_screening = state.get("passed_screening", [])

    screening_eval = recruitment_evaluate_screening(_summarise_screened(
        state.get("screened_candidates", [])
    ))
    reasoning_log.append(f"SCREENING EVAL: {screening_eval.get('reasoning', '')}")

    log_supervisor_decision(run_id, "recruitment_supervisor", "screening_evaluated",
                            screening_eval.get("reasoning", ""), screening_eval)

    print(f"[Recruitment Supervisor] {len(passed_screening)}/{len(sourced)} passed screening")

    if not passed_screening:
        report = recruitment_generate_report(
            f"Sourced: {len(sourced)}, Passed screening: 0, Accepted: 0"
        )
        return {
            **state,
            "recruitment_report": {
                "from_supervisor": "recruitment",
                "to_supervisor": "root",
                "status": "partial",
                "summary": "All candidates rejected at screening.",
                "candidates": [],
                "metadata": {"reasoning": reasoning_log, "report": report}
            },
            "recruitment_reasoning": reasoning_log
        }

    # ── STEP 3: Assess candidates ─────────────────────────────────────────────
    print(f"[Recruitment Supervisor] → Dispatching Assessment Agent ({len(passed_screening)} candidates)")
    state = run_assessment(state)
    passed_assessment = state.get("passed_assessment", [])

    assessment_eval = recruitment_evaluate_assessment(_summarise_assessed(
        state.get("assessed_candidates", [])
    ))
    reasoning_log.append(f"ASSESSMENT EVAL: {assessment_eval.get('reasoning', '')}")

    log_supervisor_decision(run_id, "recruitment_supervisor", "assessment_evaluated",
                            assessment_eval.get("reasoning", ""), assessment_eval)

    print(f"[Recruitment Supervisor] {len(passed_assessment)}/{len(passed_screening)} passed assessment | "
          f"Cohort: {assessment_eval.get('cohort_strength')}")

    if not passed_assessment:
        report = recruitment_generate_report(
            f"Sourced: {len(sourced)}, Passed screening: {len(passed_screening)}, "
            f"Passed assessment: 0, Accepted: 0"
        )
        return {
            **state,
            "recruitment_report": {
                "from_supervisor": "recruitment",
                "to_supervisor": "root",
                "status": "partial",
                "summary": "No candidates passed assessment.",
                "candidates": [],
                "metadata": {"reasoning": reasoning_log, "report": report}
            },
            "recruitment_reasoning": reasoning_log
        }

    # ── STEP 4: Schedule interviews — this also starts the TL pending timer ──
    print(f"[Recruitment Supervisor] → Dispatching Scheduler Agent")
    state = run_scheduler(state)
    print(f"[Recruitment Supervisor] {len(state.get('scheduled_candidates', []))} candidates "
          f"now awaiting TL decision (single binary Approve/Reject, {TL_APPROVAL_TIMEOUT_HOURS}h window)")

    # ── STEP 5: TL approval — REAL human decision only ───────────────────────
    tl_approved_now = get_candidates_by_stage("tl_approved")
    auto_approved = [
        {**c, "candidate_id": c["id"], "tl_decision": "approved"}
        for c in tl_approved_now
    ]
    state = {**state, "tl_approved_candidates": auto_approved}
    print(f"[Recruitment Supervisor] {len(auto_approved)} candidates have a real TL approval on file")

    # ── STEP 6: Generate offers for TL-approved candidates ────────────────────
    if auto_approved:
        print(f"[Recruitment Supervisor] → Dispatching Offer Agent")
        state = run_offer(state)

    # ── STEP 7: Offer acceptance — REAL human decision via Candidate Portal ──
    accepted_rows = get_candidates_by_stage("offer_accepted")
    accepted = [{**c, "candidate_id": c["id"], "offer_accepted": True} for c in accepted_rows]
    state = {**state, "accepted_candidates": accepted}
    print(f"[Recruitment Supervisor] {len(accepted)} candidates have accepted their offer via the portal")

    # ── STEP 8: Generate report for Root ─────────────────────────────────────
    # We pass the EXACT true state of the pipeline to the LLM so it can decide.
    pipeline_summary = (
        f"Sourced: {len(sourced)} | Passed screening: {len(passed_screening)} | "
        f"Passed assessment: {len(passed_assessment)} | TL approved: {len(auto_approved)} | "
        f"Offers Accepted: {len(accepted)}"
    )
    report = recruitment_generate_report(pipeline_summary)
    reasoning_log.append(f"FINAL REPORT: {json.dumps(report)}")

    log_supervisor_decision(run_id, "recruitment_supervisor", "complete",
                            pipeline_summary, report)

    print(f"[Recruitment Supervisor] ✓ Complete. {len(accepted)} candidates accepted offers.")

    return {
        **state,
        "recruitment_report": {
            "from_supervisor": "recruitment",
            "to_supervisor": "root",
            "status": "complete",
            "summary": pipeline_summary,
            "candidates": accepted,
            "metadata": {"reasoning": reasoning_log, "report": report}
        },
        "recruitment_reasoning": reasoning_log
    }