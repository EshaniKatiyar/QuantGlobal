"""
Sourcer Agent.
Sources real Delhi-NCR quant candidates via GitHub API and Google CSE.
Falls back to mock only if both APIs return nothing.
Checks blacklist before adding any candidate.

Feedback Loop 1 (Revised Plan §12): tracks which source (GitHub vs Google)
historically yields candidates that pass screening, and queries that source
harder on subsequent runs.
"""

from core.tools import search_github_candidates, search_google_candidates, get_mock_candidates
from database.db import add_candidate, is_blacklisted, log_action, record_sourced, get_source_ranking, get_conn
from config import MIN_LEADS
from database.db import get_active_candidate_count

def _already_in_pipeline(email: str) -> bool:
    """Stops the same candidate (esp. mock fallback ones) from being
    re-added as a brand-new row every run."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT 1 FROM candidates WHERE email = ?", (email,))
    exists = c.fetchone() is not None
    conn.close()
    return exists


def run_sourcer(state: dict) -> dict:
    print("[Sourcer] Starting candidate sourcing...")
    
    MAX_CAPACITY = 5 
    active_count = get_active_candidate_count()
    
    if active_count >= MAX_CAPACITY:
        print(f"[Sourcer] Pipeline at MAX CAPACITY ({active_count}/{MAX_CAPACITY}). Bypassing sourcing to clear the backlog.")
        return state 
        
    spots_left = MAX_CAPACITY - active_count
    print(f"[Sourcer] Pipeline capacity at {active_count}/{MAX_CAPACITY}. Hunting for exactly {spots_left} new candidate(s)...")
    
    state["spots_left"] = spots_left
    print(f"[Sourcer] Spots left: {spots_left}")
    
    ranking = get_source_ranking()
    github_rank = next((r for r in ranking if r["source"] == "GitHub"), None)
    google_rank = next((r for r in ranking if r["source"] == "Google"), None)
    retry = False
    github_base, google_base = 10, 5
    if retry:
        github_base, google_base = 15, 8

    if github_rank and google_rank and github_rank["sourced_count"] >= 5 and google_rank["sourced_count"] >= 5:
        if github_rank["yield_rate"] >= google_rank["yield_rate"]:
            github_base, google_base = int(github_base * 1.5), int(google_base * 0.7)
            print(f"[Sourcer] GitHub has higher screening yield "
                  f"({github_rank['yield_rate']:.0%} vs {google_rank['yield_rate']:.0%}) — querying it harder")
        else:
            github_base, google_base = int(github_base * 0.7), int(google_base * 1.5)
            print(f"[Sourcer] Google has higher screening yield "
                  f"({google_rank['yield_rate']:.0%} vs {github_rank['yield_rate']:.0%}) — querying it harder")

    github_candidates = search_github_candidates(max_results=max(github_base, 3))
    google_candidates = search_google_candidates(max_results=max(google_base, 2))

    all_raw = github_candidates + google_candidates

    # Deduplicate by email
    seen_emails = set()
    unique = []
    for c in all_raw:
        if c["email"] not in seen_emails:
            seen_emails.add(c["email"])
            unique.append(c)

    # Only use mock if real APIs returned nothing at all
    if not unique:
        print("[Sourcer] No real candidates found — using mock fallback")
        unique = get_mock_candidates(MIN_LEADS)

    # Blacklist filter + save to DB
    added = []
    source_counts = {}
    for c in unique:
        if is_blacklisted(c["email"]):
            print(f"[Sourcer] {c['name']} is blacklisted — skipping")
            continue
        if _already_in_pipeline(c["email"]):
            print(f"[Sourcer] {c['name']} already in pipeline — skipping duplicate")
            continue

        candidate_id = add_candidate(
            name=c["name"],
            github_url=c["github_url"],
            email=c["email"],
            role=c["role"],
            source=c["source"]
        )

        enriched = {**c, "candidate_id": candidate_id}
        added.append(enriched)
        source_counts[c["source"]] = source_counts.get(c["source"], 0) + 1

        log_action(
            candidate_id, "sourcing", "candidate_added",
            f"Source: {c['source']} | Role: {c['role']} | "
            f"Repos: {len(c.get('repos', []))} | Stars: {c.get('stars', 0)}"
        )
        print(f"[Sourcer] + {c['name']} | {c['role']} | {c['source']}")

    # Loop 1: record sourcing volume per channel for next run's prioritisation
    for source, count in source_counts.items():
        record_sourced(source, count)

    print(f"[Sourcer] Done: {len(added)} candidates added to pipeline")

    return {**state, "sourced_candidates": added, "stage": "screening"}