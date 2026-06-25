"""
Offer Agent.
Cerebras writes a personalized offer letter for each approved candidate.
Generates Candidate Portal credentials.
"""

import bcrypt
from core.llm import generate_offer_letter
from database.db import update_candidate_stage, log_action, create_user

def run_offer(state: dict) -> dict:
    approved = state.get("tl_approved_candidates", [])
    offered = []

    for candidate in approved:
        candidate_id = candidate["candidate_id"]
        name = candidate["name"]
        role = candidate["role"]
        email = candidate.get("email", f"candidate{candidate_id}@mock.com")
        alpha_v1 = candidate.get("alpha_v1", 0)
        strengths = candidate.get("key_strengths", "strong quantitative background")

        print(f"[Offer] Generating personalized offer for {name}...")

        offer_text = generate_offer_letter(name, role, alpha_v1, strengths)

        # --- THE FIX: Password matches the username ---
        username = email.split("@")[0].lower().replace(".", "_")
        raw_password = username  # Password is now identical to the username
        password_hash = bcrypt.hashpw(raw_password.encode(), bcrypt.gensalt()).decode()
        
        create_user(username, password_hash, "Candidate", candidate_id)
        # --------------------------------------------------
        # --------------------------------------------------

        update_candidate_stage(candidate_id, "offer_sent")
        
        # Update the database log to save the ACTUAL offer letter text
        log_action(candidate_id, "offer", "offer_generated", offer_text)

        print(f"[Offer] ✓ Offer letter generated for {name}")
        print(f"          🔑 Portal Login -> Username: {username} | Password: {raw_password}")

        offered.append({**candidate, "offer_letter": offer_text, "offer_accepted": None})

    return {**state, "offered_candidates": offered, "stage": "onboarding"}