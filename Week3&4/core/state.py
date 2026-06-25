"""
Shared state schema for the entire pipeline.
Every supervisor and agent reads/writes from this single state object.
LangGraph passes this between nodes automatically.
"""

from typing import TypedDict, List, Dict, Any, Optional


class CandidateRecord(TypedDict, total=False):
    candidate_id: int
    name: str
    github_url: str
    email: str
    role: str                    # "Quant Researcher" | "Algo Trader"
    source: str                  # "GitHub" | "Google" | "Mock"
    repos: List[str]
    bio: str
    stars: int
    institute: str
    years_experience: float
    alpha_v1: float
    alpha_v2: float
    github_signal: float
    background_fit: float
    assessment_score: float
    screening_passed: bool
    assessment_passed: bool
    tl_decision: Optional[str]   # "approved" | "rejected" | None
    offer_accepted: Optional[bool]
    trainee_username: str
    trainee_password: str
    weekly_scores: List[float]
    weak_topics: List[str]
    final_decision: str          # "PPO" | "Talent Pool" | "Offboard"
    interview: Dict[str, Any]
    offer_letter: str


class SupervisorMessage(TypedDict):
    """Structured message passed between supervisors."""
    from_supervisor: str
    to_supervisor: str
    status: str                  # "dispatching" | "complete" | "failed" | "retry"
    summary: str                 # LLM-generated summary of what happened
    candidates: List[CandidateRecord]
    metadata: Dict[str, Any]


class PipelineState(TypedDict, total=False):
    # --- Meta ---
    run_id: int
    stage: str
    root_reasoning: List[str]
    recruitment_reasoning: List[str]
    ld_reasoning: List[str]

    # --- Recruitment Phase ---
    sourced_candidates: List[CandidateRecord]
    passed_screening: List[CandidateRecord]
    passed_assessment: List[CandidateRecord]
    scheduled_candidates: List[CandidateRecord]
    tl_approved_candidates: List[CandidateRecord]
    offered_candidates: List[CandidateRecord]
    accepted_candidates: List[CandidateRecord]

    # --- L&D Phase ---
    onboarded_candidates: List[CandidateRecord]
    current_trainees: List[CandidateRecord]
    current_week: int
    coached_candidates: List[CandidateRecord]
    quiz_results: List[CandidateRecord]
    early_offboarded: List[CandidateRecord]

    # --- Final ---
    ppo_candidates: List[CandidateRecord]
    talent_pool_candidates: List[CandidateRecord]
    offboarded_candidates: List[CandidateRecord]

    # --- Supervisor messages ---
    recruitment_report: SupervisorMessage
    ld_report: SupervisorMessage

    # --- Pipeline health ---
    retry_count: int
    pipeline_failed: bool
    failure_reason: str