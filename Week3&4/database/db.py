import os
import sqlite3
import hashlib
import json
from datetime import datetime, timedelta
from config import FAILED_CANDIDATE_RETENTION_DAYS, OFFBOARDED_RETENTION_DAYS

DB_PATH = "database/quantglobal.db"

os.makedirs("database", exist_ok=True)
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            github_url TEXT,
            email TEXT,
            role TEXT,
            source TEXT,
            alpha_score_v1 REAL DEFAULT 0,
            alpha_score_v2 REAL DEFAULT 0,
            stage TEXT DEFAULT 'sourced',
            status TEXT DEFAULT 'active',
            consent_given INTEGER DEFAULT 0,
            consent_timestamp TEXT,
            password_hash TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            tl_pending_since TEXT
        );

        CREATE TABLE IF NOT EXISTS blacklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email_hash TEXT UNIQUE,
            phone_hash TEXT,
            reason TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS talent_pool (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER,
            alpha_score_v2 REAL,
            re_engage_after TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(candidate_id) REFERENCES candidates(id)
        );

        CREATE TABLE IF NOT EXISTS quiz_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER,
            week INTEGER,
            topic TEXT,
            score REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(candidate_id) REFERENCES candidates(id)
        );

        CREATE TABLE IF NOT EXISTS pipeline_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER,
            stage TEXT,
            action TEXT,
            result TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(candidate_id) REFERENCES candidates(id)
        );

        CREATE TABLE IF NOT EXISTS supervisor_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            supervisor TEXT,
            action TEXT,
            reasoning TEXT,
            metadata TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS pipeline_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trigger_type TEXT,
            started_at TEXT DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT,
            candidates_sourced INTEGER DEFAULT 0,
            status TEXT DEFAULT 'running'
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash TEXT,
            role TEXT,
            candidate_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS stage_durations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stage TEXT,
            duration_hours REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS supervisor_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            supervisor TEXT,
            action TEXT,
            reasoning TEXT,
            metadata TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()


# --- Candidate Operations ---

def add_candidate(name, github_url, email, role, source):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO candidates (name, github_url, email, role, source)
        VALUES (?, ?, ?, ?, ?)
    """, (name, github_url, email, role, source))
    candidate_id = c.lastrowid
    conn.commit()
    conn.close()
    return candidate_id


def get_candidate(candidate_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_candidates():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM candidates ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_candidate_stage(candidate_id, stage, status=None):
    conn = get_conn()
    c = conn.cursor()
    if status:
        c.execute("""
            UPDATE candidates SET stage = ?, status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (stage, status, candidate_id))
    else:
        c.execute("""
            UPDATE candidates SET stage = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (stage, candidate_id))
    conn.commit()
    conn.close()


def update_alpha_score(candidate_id, v1=None, v2=None):
    conn = get_conn()
    c = conn.cursor()
    if v1 is not None:
        c.execute("UPDATE candidates SET alpha_score_v1 = ? WHERE id = ?", (v1, candidate_id))
    if v2 is not None:
        c.execute("UPDATE candidates SET alpha_score_v2 = ? WHERE id = ?", (v2, candidate_id))
    conn.commit()
    conn.close()


def set_consent(candidate_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        UPDATE candidates SET consent_given = 1, consent_timestamp = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (candidate_id,))
    conn.commit()
    conn.close()


# --- Blacklist Operations ---

def hash_identifier(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode()).hexdigest()


def add_to_blacklist(email: str, phone: str = None, reason: str = ""):
    conn = get_conn()
    c = conn.cursor()
    email_hash = hash_identifier(email)
    phone_hash = hash_identifier(phone) if phone else None
    try:
        c.execute("""
            INSERT INTO blacklist (email_hash, phone_hash, reason)
            VALUES (?, ?, ?)
        """, (email_hash, phone_hash, reason))
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # already blacklisted
    conn.close()


def is_blacklisted(email: str) -> bool:
    conn = get_conn()
    c = conn.cursor()
    email_hash = hash_identifier(email)
    c.execute("SELECT 1 FROM blacklist WHERE email_hash = ?", (email_hash,))
    result = c.fetchone()
    conn.close()
    return result is not None


# --- Talent Pool ---

def add_to_talent_pool(candidate_id, alpha_score_v2):
    conn = get_conn()
    c = conn.cursor()
    re_engage = (datetime.now() + timedelta(days=180)).isoformat()
    c.execute("""
        INSERT INTO talent_pool (candidate_id, alpha_score_v2, re_engage_after)
        VALUES (?, ?, ?)
    """, (candidate_id, alpha_score_v2, re_engage))
    conn.commit()
    conn.close()


# --- Quiz Scores ---

def save_quiz_score(candidate_id, week, topic, score):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO quiz_scores (candidate_id, week, topic, score)
        VALUES (?, ?, ?, ?)
    """, (candidate_id, week, topic, score))
    conn.commit()
    conn.close()


def get_quiz_scores(candidate_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT week, topic, score FROM quiz_scores
        WHERE candidate_id = ? ORDER BY week, topic
    """, (candidate_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_weak_topics(candidate_id, week, threshold=60):
    scores = get_quiz_scores(candidate_id)
    week_scores = [s for s in scores if s["week"] == week]
    return [s["topic"] for s in week_scores if s["score"] < threshold]


# --- Pipeline Logs ---

def log_action(candidate_id, stage, action, result):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO pipeline_logs (candidate_id, stage, action, result)
        VALUES (?, ?, ?, ?)
    """, (candidate_id, stage, action, result))
    conn.commit()
    conn.close()


def get_logs(candidate_id=None):
    conn = get_conn()
    c = conn.cursor()
    if candidate_id:
        c.execute("SELECT * FROM pipeline_logs WHERE candidate_id = ? ORDER BY timestamp DESC", (candidate_id,))
    else:
        c.execute("SELECT * FROM pipeline_logs ORDER BY timestamp DESC LIMIT 200")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Stage Duration (for Hiring Velocity) ---

def log_stage_duration(stage, duration_hours):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO stage_durations (stage, duration_hours) VALUES (?, ?)", (stage, duration_hours))
    conn.commit()
    conn.close()


def get_avg_stage_duration(stage):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT AVG(duration_hours) FROM stage_durations WHERE stage = ?", (stage,))
    result = c.fetchone()
    conn.close()
    return result[0] if result[0] else 2.0  # default 2hr per stage


# --- User Auth ---

def create_user(username, password_hash, role, candidate_id=None):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO users (username, password_hash, role, candidate_id)
            VALUES (?, ?, ?, ?)
        """, (username, password_hash, role, candidate_id))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()


def get_user(username):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


# --- Data Retention Cleanup ---

def run_retention_cleanup():
    conn = get_conn()
    c = conn.cursor()
    cutoff_failed = (datetime.now() - timedelta(days=FAILED_CANDIDATE_RETENTION_DAYS)).isoformat()
    cutoff_offboarded = (datetime.now() - timedelta(days=OFFBOARDED_RETENTION_DAYS)).isoformat()

    # Anonymise failed candidates
    c.execute("""
        UPDATE candidates
        SET email = 'anonymised', name = 'anonymised', github_url = 'anonymised'
        WHERE status = 'rejected' AND updated_at < ?
    """, (cutoff_failed,))

    # Anonymise offboarded trainees
    c.execute("""
        UPDATE candidates
        SET email = 'anonymised', name = 'anonymised', github_url = 'anonymised'
        WHERE status = 'offboarded' AND updated_at < ?
    """, (cutoff_offboarded,))

    conn.commit()
    conn.close()


# --- Supervisor Decision Logging ---

def log_supervisor_decision(run_id: int, supervisor: str, action: str,
                             reasoning: str, metadata: dict):
    """Log every supervisor-level decision for auditability."""
    import json
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS supervisor_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            supervisor TEXT,
            action TEXT,
            reasoning TEXT,
            metadata TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        INSERT INTO supervisor_logs (run_id, supervisor, action, reasoning, metadata)
        VALUES (?, ?, ?, ?, ?)
    """, (run_id, supervisor, action, reasoning, json.dumps(metadata)))
    conn.commit()
    conn.close()


def get_supervisor_logs(run_id: int = None):
    conn = get_conn()
    c = conn.cursor()
    if run_id:
        c.execute("SELECT * FROM supervisor_logs WHERE run_id = ? ORDER BY timestamp DESC", (run_id,))
    else:
        c.execute("SELECT * FROM supervisor_logs ORDER BY timestamp DESC LIMIT 100")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Sourcing Feedback Loop ---

def log_source_yield(source: str, candidate_id: int, passed_screening: bool, passed_assessment: bool):
    """Track which source produces better candidates over time."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS source_yield (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            candidate_id INTEGER,
            passed_screening INTEGER,
            passed_assessment INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        INSERT INTO source_yield (source, candidate_id, passed_screening, passed_assessment)
        VALUES (?, ?, ?, ?)
    """, (source, candidate_id, int(passed_screening), int(passed_assessment)))
    conn.commit()
    conn.close()


def get_source_yield_stats() -> dict:
    """Returns pass rates per source. Used by Sourcer to prioritise best source."""
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("""
            SELECT source,
                COUNT(*) as total,
                SUM(passed_screening) as passed_screen,
                SUM(passed_assessment) as passed_assess
            FROM source_yield GROUP BY source
        """)
        rows = c.fetchall()
        conn.close()
        stats = {}
        for r in rows:
            total = r["total"] or 1
            stats[r["source"]] = {
                "total": total,
                "screen_rate": round(r["passed_screen"] / total * 100, 1),
                "assess_rate": round(r["passed_assess"] / total * 100, 1),
            }
        return stats
    except Exception:
        conn.close()
        return {}


# --- Alpha Score Calibration Flag (Loop 2) ---

def log_alpha_calibration(candidate_id: int, alpha_v1: float, alpha_v2: float):
    """Compare v1 prediction vs v2 outcome. Flags drift for review."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS alpha_calibration (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER,
            alpha_v1 REAL,
            alpha_v2 REAL,
            drift REAL,
            flag TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    drift = alpha_v2 - (alpha_v1 * 100 / 75)  # normalise v1 to 100-scale for comparison
    flag = "HIGH_DRIFT" if abs(drift) > 20 else "OK"
    c.execute("""
        INSERT INTO alpha_calibration (candidate_id, alpha_v1, alpha_v2, drift, flag)
        VALUES (?, ?, ?, ?, ?)
    """, (candidate_id, alpha_v1, alpha_v2, round(drift, 2), flag))
    conn.commit()
    conn.close()
    if flag == "HIGH_DRIFT":
        print(f"[Alpha Calibration] ⚠️  Candidate #{candidate_id} — "
              f"v1: {alpha_v1:.1f}, v2: {alpha_v2:.1f}, drift: {drift:.1f} — FLAG: {flag}")


def get_alpha_calibration_flags() -> list:
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT * FROM alpha_calibration WHERE flag = 'HIGH_DRIFT' ORDER BY created_at DESC")
        rows = c.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        conn.close()
        return []


# --- Missing functions referenced across agents ---

def get_candidates_by_stage(stage: str) -> list:
    """Returns all candidates at a given stage."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM candidates WHERE stage = ?", (stage,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_overdue_tl_pending(timeout_hours: int) -> list:
    """Returns candidates scheduled but with no TL decision past the timeout window."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM candidates
        WHERE stage = 'scheduled'
        AND status = 'active'
        AND tl_pending_since IS NOT NULL
        AND (julianday('now') - julianday(tl_pending_since)) * 24 > ?
    """, (timeout_hours,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def flag_tl_overdue(candidate_id: int):
    """Flags a candidate as TL-decision overdue without changing their stage."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        UPDATE candidates SET status = 'tl_overdue', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (candidate_id,))
    conn.commit()
    conn.close()


def mark_tl_pending(candidate_id: int):
    """Records the moment a candidate enters TL approval queue."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        UPDATE candidates SET tl_pending_since = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (candidate_id,))
    conn.commit()
    conn.close()


def record_sourced(source: str, count: int):
    """Feedback Loop 1: log how many candidates were sourced from each channel."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS source_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            sourced_count INTEGER DEFAULT 0,
            passed_screening_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        INSERT INTO source_stats (source, sourced_count)
        VALUES (?, ?)
    """, (source, count))
    conn.commit()
    conn.close()


def record_passed_screening(source: str, count: int):
    """Feedback Loop 1: log how many candidates from each source passed screening."""
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("""
            UPDATE source_stats SET passed_screening_count = passed_screening_count + ?
            WHERE source = ? AND id = (
                SELECT id FROM source_stats WHERE source = ? ORDER BY created_at DESC LIMIT 1
            )
        """, (count, source, source))
        conn.commit()
    except Exception:
        pass
    conn.close()


def get_source_ranking() -> list:
    """Feedback Loop 1: returns sources ranked by screening yield rate."""
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("""
            SELECT source,
                SUM(sourced_count) as sourced_count,
                SUM(passed_screening_count) as passed_count,
                CASE WHEN SUM(sourced_count) > 0
                    THEN CAST(SUM(passed_screening_count) AS FLOAT) / SUM(sourced_count)
                    ELSE 0 END as yield_rate
            FROM source_stats
            GROUP BY source
            ORDER BY yield_rate DESC
        """)
        rows = c.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        conn.close()
        return []


def log_calibration_check(run_id: int, avg_v1_top: float, avg_v2_top: float,
                           flagged: bool, note: str):
    """Feedback Loop 2: log Alpha Score calibration check results."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS calibration_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            avg_v1_top_quartile REAL,
            avg_v2_top_quartile REAL,
            flagged INTEGER,
            note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        INSERT INTO calibration_checks (run_id, avg_v1_top_quartile, avg_v2_top_quartile, flagged, note)
        VALUES (?, ?, ?, ?, ?)
    """, (run_id, avg_v1_top, avg_v2_top, int(flagged), note))
    conn.commit()
    conn.close()

def get_calibration_flags() -> list:
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT * FROM calibration_checks WHERE flagged = 1 ORDER BY created_at DESC")
        rows = c.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        conn.close()
        return []
def get_cohort_topic_trends() -> list:
    conn = get_conn()
    c = conn.cursor()
    try:
        # ADDED 'as n' to the count so the dashboard finds the key it expects
        c.execute("""
            SELECT topic, AVG(score) as avg_score, COUNT(*) as n
            FROM quiz_scores
            GROUP BY topic
            ORDER BY avg_score ASC
        """)
        rows = c.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        conn.close()
        return []
    
def update_alpha_v2(candidate_id, alpha_v2):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE candidates SET alpha_score_v2 = ? WHERE id = ?", (alpha_v2, candidate_id))
        try:
            cursor.execute("UPDATE candidates SET alpha_v2 = ? WHERE id = ?", (alpha_v2, candidate_id))
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE candidates ADD COLUMN alpha_v2 REAL")
            cursor.execute("UPDATE candidates SET alpha_v2 = ? WHERE id = ?", (alpha_v2, candidate_id))
        conn.commit()


def reset_trainee_password(candidate_id):
    """Generates a fresh random password for an already-onboarded trainee
    and returns the raw password so HR can hand it to them directly,
    instead of having to dig through terminal logs."""
    import bcrypt
    import string
    import random

    raw_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    password_hash = bcrypt.hashpw(raw_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET password_hash = ? WHERE candidate_id = ?",
            (password_hash, candidate_id)
        )
        conn.commit()

    log_action(candidate_id, "onboarding", "password_reset_manual",
               "Trainee password reset by HR via dashboard")

    return raw_password
    
def save_candidate_code(candidate_id: str, questions: dict, answers: dict):
    """Saves the raw JSON questions and code answers to the database."""
    import sqlite3
    import json
    # Use your actual database filename here
    conn = sqlite3.connect(DB_PATH) 
    cursor = conn.cursor()
    
    try:
        cursor.execute("UPDATE candidates SET questions = ?, answers = ? WHERE id = ?", 
                       (json.dumps(questions), json.dumps(answers), candidate_id))
    except sqlite3.OperationalError:
        # If the columns don't exist yet, build them dynamically!
        cursor.execute("ALTER TABLE candidates ADD COLUMN questions TEXT")
        cursor.execute("ALTER TABLE candidates ADD COLUMN answers TEXT")
        cursor.execute("UPDATE candidates SET questions = ?, answers = ? WHERE id = ?", 
                       (json.dumps(questions), json.dumps(answers), candidate_id))
        
    conn.commit()
    conn.close()

def get_active_candidate_count():
    """Counts how many candidates are currently taking up pipeline capacity."""
    import sqlite3
    try:
        # 1. MAKE SURE THIS PATH MATCHES YOUR REAL DB (e.g., "database/qg.db")
        with sqlite3.connect(DB_PATH) as conn: 
            cursor = conn.cursor()
            
            # 2. BULLETPROOF SQL: Using LOWER() so we don't care if it is 'Active', 'ACTIVE', or 'active'
            cursor.execute("""
                SELECT COUNT(*) FROM candidates 
                WHERE LOWER(status) = 'active' 
                AND LOWER(stage) NOT IN ('onboarded', 'talent_pool', 'rejected', 'tl_rejected')
            """)
            count = cursor.fetchone()[0]
            
            # 3. LOUD DEBUGGING: Print the exact number so we can see it in the terminal!
            print(f"🕵️ [DB DEBUG] I see exactly {count} active candidates taking up space.")
            return count
            
    except Exception as e:
        print(f"🚨 [DB ERROR] The counter crashed: {e}")
        return 0
    
def update_candidate_password(candidate_id, password_hash):
    import sqlite3
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE candidates SET password_hash = ? WHERE id = ?", (password_hash, candidate_id))
        conn.commit()