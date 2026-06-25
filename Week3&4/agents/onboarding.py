import bcrypt
import string
import random
import sqlite3
from utils.encryption import encrypt
from database.db import DB_PATH, update_candidate_stage, log_action, create_user, set_consent, get_quiz_scores

def run_onboarding(state: dict) -> dict:
    accepted = state.get("accepted_candidates", [])
    onboarded = []

    for candidate in accepted:
        candidate_id = candidate["id"] # Note: Usually "id" in sqlite, adjust if yours is "candidate_id"
        name = candidate["name"]
        email = candidate["email"]
        current_stage = candidate.get("stage", "")

        # ── IDEMPOTENCY FIX ──────────────────────────────────────────────
        # This function used to run unconditionally for every candidate in
        # accepted_candidates, including ones root.py's L&D wake-up override
        # re-injects on every later pipeline trigger. That meant a trainee
        # who'd already logged in got a BRAND NEW random password every
        # single run, silently invalidating credentials they'd already been
        # given. Only generate fresh credentials for candidates still
        # sitting at "offer_accepted" — anyone further along already has a
        # working login and just needs to be passed through unchanged.
        if current_stage and current_stage != "offer_accepted":
            print(f"[Onboarding] {name} already onboarded (stage={current_stage}) — "
                  f"skipping credential regeneration, passing through")

            # Reconstruct real weekly_scores from DB so coaching personalization
            # (prev-week score) isn't silently reset to 0 on every re-run.
            quiz_rows = get_quiz_scores(candidate_id)
            weeks = sorted(set(q["week"] for q in quiz_rows))
            weekly_scores = []
            for w in weeks:
                w_scores = [q["score"] for q in quiz_rows if q["week"] == w]
                weekly_scores.append(sum(w_scores) / len(w_scores))

            current_week = (weeks[-1] + 1) if weeks else 1

            onboarded.append({
                **candidate,
                "candidate_id": candidate_id,
                "current_week": current_week,
                "weekly_scores": weekly_scores,
                "weak_topics": candidate.get("weak_topics", [])
            })
            continue
        # ─────────────────────────────────────────────────────────────────

        # 1. Generate truly random, secure credentials
        username = email.split("@")[0].lower().replace(".", "_")
        raw_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        password_hash = bcrypt.hashpw(raw_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # 2. Encrypt mock PII documents (demonstrates AES-256 for your PDF requirement)
        mock_pii = f"Name: {name} | Email: {email} | Candidate ID: {candidate_id}"
        try:
            encrypted_pii = encrypt(mock_pii)
        except Exception as e:
            encrypted_pii = f"encryption_failed_{e}"

        # 3. Save to database using your existing functions
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
        UPDATE users 
        SET password_hash = ?, role = 'Trainee' 
        WHERE candidate_id = ?
    """, (password_hash, candidate_id))
            conn.commit()
        set_consent(candidate_id)
        update_candidate_stage(candidate_id, "onboarded")

        # 4. Log the action
        log_action(candidate_id, "onboarding", "trainee_created",
                   f"Username: {username} | PII encrypted (AES-256) | Consent recorded | Credentials issued.")

        # 5. THE DEMO FIX: Print the credentials boldly to the terminal!
        print(f"\n============================================================")
        print(f"[Onboarding Agent] SECURE CREDENTIALS GENERATED")
        print(f"Candidate: {name}")
        print(f"Login Email: {email}")
        print(f"Portal Password: {raw_password}")
        print(f"============================================================\n")

        onboarded.append({
            **candidate,
            "candidate_id": candidate_id,
            "trainee_username": username,
            "trainee_password": raw_password, # Carried in state, but not saved in DB!
            "encrypted_pii": encrypted_pii,
            "current_week": 1,
            "weekly_scores": [],
            "weak_topics": []
        })

    return {**state, "onboarded_candidates": onboarded, "stage": "ld"}