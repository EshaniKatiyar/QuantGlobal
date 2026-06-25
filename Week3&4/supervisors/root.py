"""
Root Supervisor — QuantGlobal AI Recruitment System.
Top-level LLM-driven orchestrator.
Dispatches Recruitment and L&D team supervisors.
Makes pipeline-level decisions. All reasoning is logged.
"""

import json
from langgraph.graph import StateGraph, END
from core.state import PipelineState
from core.llm import (
    root_decide_next_action,
    root_evaluate_recruitment_report,
    root_evaluate_ld_report
)
from database.db import init_db, log_supervisor_decision, log_calibration_check
from supervisors.recruitment import run_recruitment_supervisor
from supervisors.ld import run_ld_supervisor
from database.db import get_active_candidate_count


# ─────────────────────────────────────────────
# ROOT NODES
# ─────────────────────────────────────────────

def root_init(state: PipelineState) -> PipelineState:
    """Root Supervisor initialises the pipeline."""
    init_db()
    run_id = state.get("run_id", 1)

    print(f"\n{'='*60}")
    print(f"  QUANTGLOBAL AI RECRUITMENT SYSTEM")
    print(f"  Root Supervisor | Run #{run_id}")
    print(f"{'='*60}")

    # Root LLM decides initial action
    state_summary = (
        f"New pipeline run initiated. Run ID: {run_id}. "
        f"Objective: Source, screen, hire, and develop quant talent "
        f"(Quant Researcher / Algo Trader roles) from Delhi-NCR. "
        f"All stages must complete autonomously."
    )
    decision = root_decide_next_action(state_summary)

    reasoning = [f"INIT: {decision.get('reasoning', 'Starting pipeline')}"]
    print(f"[Root] Decision: {decision.get('action')} | Reasoning: {decision.get('reasoning', '')[:100]}")

    if decision.get("alert"):
        print(f"[Root] ⚠️  Alert: {decision.get('alert')}")

    log_supervisor_decision(run_id, "root_supervisor", "initialised",
                            decision.get("reasoning", ""), decision)

    return {
        **state,
        "stage": "recruitment",
        "root_reasoning": reasoning,
        "retry_count": 0,
        "recruitment_instructions": decision.get("instructions", ""),
        "pipeline_failed": False
    }


def root_dispatch_recruitment(state: PipelineState) -> PipelineState:
    """Root dispatches Recruitment Team Supervisor."""
    run_id = state.get("run_id", 1)
    print(f"\n[Root] ▶ Dispatching Recruitment Team Supervisor")

    state = run_recruitment_supervisor(state)

    report = state.get("recruitment_report", {})
    report_str = json.dumps(report.get("metadata", {}).get("report", {}), indent=2)
    evaluation = root_evaluate_recruitment_report(
        f"Status: {report.get('status')}\n"
        f"Summary: {report.get('summary')}\n"
        f"Report: {report_str}"
    )

    reasoning = state.get("root_reasoning", [])
    reasoning.append(f"RECRUITMENT RESULT: {evaluation.get('reasoning', '')}")

    if evaluation.get("tl_alert"):
        print(f"[Root] ⚠️  TL Alert: {evaluation.get('tl_alert')}")

    log_supervisor_decision(run_id, "root_supervisor", "recruitment_evaluated",
                            evaluation.get("reasoning", ""), evaluation)

    print(f"[Root] Recruitment cohort quality: {evaluation.get('cohort_quality')} | "
          f"Proceed to L&D: {evaluation.get('proceed_to_ld')}")
    # --- AUTONOMOUS L&D WAKE-UP OVERRIDE ---
   # --- AUTONOMOUS L&D WAKE-UP OVERRIDE ---
    from database.db import get_all_candidates
    
    # Sweep the database for anyone currently in the L&D lifecycle
    all_c = get_all_candidates()
    active_ld_trainees = [
        c for c in all_c 
        if "week" in c.get("stage", "") or c.get("stage") == "onboarded" or c.get("stage") == "offer_accepted"
    ]

    if active_ld_trainees:
        proceed = True  # Force the L&D Supervisor to wake up
        print(f"[Root] ⚠️ L&D Override: Found {len(active_ld_trainees)} active trainees in DB. Forcing L&D execution.")
        
        # THE FIX: Translate DB 'id' to 'candidate_id' so upstream agents don't crash!
        for trainee in active_ld_trainees:
            if "id" in trainee:
                trainee["candidate_id"] = trainee["id"]
                
        # Inject them into the LangGraph state
        state["accepted_candidates"] = active_ld_trainees
        state["trainees"] = active_ld_trainees
    # --------------------------------------
    return {
        **state,
        "root_reasoning": reasoning,
        "proceed_to_ld": evaluation.get("proceed_to_ld", False),
        "ld_instructions": evaluation.get("instructions_for_ld", ""),
        "tl_alert": evaluation.get("tl_alert", ""),
        "stage": "ld" if evaluation.get("proceed_to_ld") else "complete"
    }


def _check_score_calibration(state: PipelineState, run_id: int):
    """Feedback Loop 2 (Revised Plan §12): if candidates who scored highest
    on Alpha v1 (pre-L&D) are NOT also the strongest performers post-L&D,
    flag the Alpha Score weights for manual review."""
    ppo = state.get("ppo_candidates", [])
    pool = state.get("talent_pool_candidates", [])
    offboarded = state.get("offboarded_candidates", [])
    all_final = ppo + pool + offboarded

    if len(all_final) < 4:
        return  # not enough cohort size for a meaningful quartile comparison

    ranked_by_v1 = sorted(all_final, key=lambda c: c.get("alpha_v1", 0), reverse=True)
    top_quartile_n = max(1, len(ranked_by_v1) // 4)
    top_quartile = ranked_by_v1[:top_quartile_n]

    avg_v1_top = sum(c.get("alpha_v1", 0) for c in top_quartile) / len(top_quartile)
    avg_v2_top = sum(c.get("alpha_v2", 0) for c in top_quartile) / len(top_quartile)
    avg_v2_all = sum(c.get("alpha_v2", 0) for c in all_final) / len(all_final)

    # Top v1 scorers should outperform the cohort average on v2. If they
    # don't (or are below the PPO line despite being top-screened), flag it.
    flagged = avg_v2_top <= avg_v2_all
    note = (
        f"Top-quartile Alpha v1 avg {avg_v1_top:.1f}/75 → Alpha v2 avg {avg_v2_top:.1f}/100, "
        f"vs cohort Alpha v2 avg {avg_v2_all:.1f}/100. "
        + ("Top screeners are NOT outperforming the cohort post-L&D — review Alpha v1 weights."
           if flagged else "Top screeners are outperforming the cohort post-L&D — weights look calibrated.")
    )
    log_calibration_check(run_id, avg_v1_top, avg_v2_top, flagged, note)
    print(f"[Root] Calibration check: {note}")
    if flagged:
        print("[Root] ⚠️  Alpha Score weight calibration flagged for manual review")


def root_dispatch_ld(state: PipelineState) -> PipelineState:
    """Root dispatches L&D Team Supervisor."""
    run_id = state.get("run_id", 1)
    print(f"\n[Root] ▶ Dispatching L&D Team Supervisor")

    state = run_ld_supervisor(state)

    report = state.get("ld_report", {})
    report_str = json.dumps(report.get("metadata", {}).get("report", {}), indent=2)
    evaluation = root_evaluate_ld_report(
        f"Status: {report.get('status')}\n"
        f"Summary: {report.get('summary')}\n"
        f"Report: {report_str}"
    )

    reasoning = state.get("root_reasoning", [])
    reasoning.append(f"L&D RESULT: {evaluation.get('reasoning', '')}")

    log_supervisor_decision(run_id, "root_supervisor", "ld_evaluated",
                            evaluation.get("reasoning", ""), evaluation)

    print(f"[Root] Pipeline health: {evaluation.get('pipeline_health')}")
    print(f"[Root] TL Summary: {evaluation.get('tl_summary', '')}")

    _check_score_calibration(state, run_id)

    return {
        **state,
        "root_reasoning": reasoning,
        "pipeline_health": evaluation.get("pipeline_health", ""),
        "pipeline_recommendations": evaluation.get("recommendations", ""),
        "tl_executive_summary": evaluation.get("tl_summary", ""),
        "stage": "complete"
    }


def root_complete(state: PipelineState) -> PipelineState:
    """Root finalises and prints summary."""
    run_id = state.get("run_id", 1)

    ppo = state.get("ppo_candidates", [])
    pool = state.get("talent_pool_candidates", [])
    offboarded = state.get("offboarded_candidates", [])
    sourced = state.get("sourced_candidates", [])
    accepted = state.get("accepted_candidates", [])

    print(f"\n{'='*60}")
    print(f"  PIPELINE COMPLETE | Run #{run_id}")
    print(f"  Sourced: {len(sourced)} | Accepted: {len(accepted)}")
    print(f"  PPO: {len(ppo)} | Talent Pool: {len(pool)} | Offboarded: {len(offboarded)}")
    print(f"  Health: {state.get('pipeline_health', 'N/A')}")
    if state.get("tl_executive_summary"):
        print(f"  TL Summary: {state.get('tl_executive_summary')}")
    print(f"{'='*60}\n")

    log_supervisor_decision(run_id, "root_supervisor", "pipeline_complete",
                            f"PPO:{len(ppo)} Pool:{len(pool)} Offboard:{len(offboarded)}", {})

    return {**state, "stage": "complete"}


# ─────────────────────────────────────────────
# ROUTING
# ─────────────────────────────────────────────

def route_after_recruitment(state: PipelineState) -> str:
    accepted = state.get("accepted_candidates", [])
    
    # THE FIX: If anyone has accepted an offer, FORCE the pipeline to run L&D.
    # Do not let the Root LLM cancel the training phase.
    if accepted:
        return "dispatch_ld"
        
    return "complete"

# ─────────────────────────────────────────────
# BUILD ROOT GRAPH
# ─────────────────────────────────────────────

def build_root_graph():
    graph = StateGraph(PipelineState)

    graph.add_node("init", root_init)
    graph.add_node("dispatch_recruitment", root_dispatch_recruitment)
    graph.add_node("dispatch_ld", root_dispatch_ld)
    graph.add_node("complete", root_complete)

    graph.set_entry_point("init")
    graph.add_edge("init", "dispatch_recruitment")

    graph.add_conditional_edges(
        "dispatch_recruitment",
        route_after_recruitment,
        {
            "dispatch_ld": "dispatch_ld",
            "complete": "complete"
        }
    )

    graph.add_edge("dispatch_ld", "complete")
    graph.add_edge("complete", END)

    return graph.compile()


root_graph = build_root_graph()


def run_pipeline(run_id: int = 1) -> dict:
    """Public entry point to run the full pipeline."""
    initial_state: PipelineState = {
        "run_id": run_id,
        "stage": "init",
        "root_reasoning": [],
        "recruitment_reasoning": [],
        "ld_reasoning": [],
        "retry_count": 0,
        "pipeline_failed": False
    }
    return root_graph.invoke(initial_state)