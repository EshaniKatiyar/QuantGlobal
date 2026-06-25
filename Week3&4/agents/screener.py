import random
from utils.alpha_score import compute_github_signal, compute_background_fit, compute_alpha_v1
from database.db import update_candidate_stage, update_alpha_score, log_action, record_passed_screening
from core.llm import call_llm, parse_json

SCREENING_THRESHOLD = 30  # minimum Alpha v1 to proceed (out of 75)

INSTITUTE_EXTRACTION_SYSTEM = """You extract structured facts from candidate bios for a
quant recruitment screening system. Be precise and conservative — if information isn't
clearly present, use the defaults."""


def extract_institute_experience(bio: str) -> tuple:
    """Uses the shared Cerebras client (core/llm.py) for consistent JSON-mode
    handling and error fallback, rather than a separate ad-hoc client."""
    result = call_llm(
        system=INSTITUTE_EXTRACTION_SYSTEM,
        user=f"""Extract institute name and years of experience from this bio.
Bio: {bio}

Return JSON:
{{
  "institute": "<name or 'Other' if not found>",
  "years_experience": <number, 0 if not found>
}}""",
        json_mode=True,
        max_tokens=100
    )
    data = parse_json(result)
    institute = data.get("institute", "Other") or "Other"
    try:
        years_exp = float(data.get("years_experience", 0))
    except (TypeError, ValueError):
        years_exp = 0.0
    return institute, years_exp


def screen_candidate(candidate: dict) -> dict:
    name = candidate.get("name", "Unknown")
    role = candidate.get("role", "Quant Researcher")
    candidate_id = candidate.get("candidate_id")
    repos = candidate.get("repos", [])
    stars = candidate.get("stars", 0)
    bio = candidate.get("bio", "")
    institute = candidate.get("institute", "Other")
    years_exp = candidate.get("years_experience", 0)
    source = candidate.get("source", "Unknown")

    print(f"[Screener] Screening {name} for {role}...")

    # --- Use shared Cerebras client to extract institute/experience from bio if not present ---
    if not institute or institute == "Other":
        try:
            extracted_institute, extracted_years = extract_institute_experience(bio)
            institute, years_exp = extracted_institute, extracted_years
        except Exception as e:
            print(f"[Screener] Cerebras extraction error: {e}")

    # --- Compute commit frequency (mock from repo count) ---
    commit_frequency = min(len(repos) * 0.8, 10)  # proxy

    # --- Compute Alpha Score components ---
    github_signal = compute_github_signal(repos, commit_frequency, stars)
    background_fit = compute_background_fit(institute, years_exp)

    # Assessment score placeholder — will be updated after Assessment Agent
    assessment_score = random.uniform(12, 20)  # mock pre-assessment estimate

    alpha_v1 = compute_alpha_v1(github_signal, background_fit, assessment_score)

    # --- Update DB ---
    update_alpha_score(candidate_id, v1=alpha_v1)

    passed = alpha_v1 >= SCREENING_THRESHOLD
    status = "screening_passed" if passed else "rejected"
    update_candidate_stage(candidate_id, "screening", status if not passed else "active")

    # Feedback Loop 1: tell the Sourcer which channel produced a screening pass
    if passed:
        record_passed_screening(source, 1)

    log_action(
        candidate_id, "screening",
        "alpha_score_v1_computed",
        f"Alpha v1: {alpha_v1} | GitHub: {github_signal} | Background: {background_fit} | Passed: {passed}"
    )

    print(f"[Screener] {name} — Alpha v1: {alpha_v1:.1f}/75 | {'PASS' if passed else 'REJECT'}")

    return {
        **candidate,
        "alpha_v1": alpha_v1,
        "github_signal": github_signal,
        "background_fit": background_fit,
        "institute": institute,
        "years_experience": years_exp,
        "screening_passed": passed
    }


def run_screener(state: dict) -> dict:
    """Main screener node for LangGraph."""
    sourced = state.get("sourced_candidates", [])
    screened = []
    passed = []

    for candidate in sourced:
        result = screen_candidate(candidate)
        screened.append(result)
        if result["screening_passed"]:
            passed.append(result)

    print(f"[Screener] {len(passed)}/{len(sourced)} candidates passed screening.")

    return {
        **state,
        "screened_candidates": screened,
        "passed_screening": passed,
        "stage": "assessment"
    }
