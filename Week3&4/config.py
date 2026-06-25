import os
import sys
import builtins
from dotenv import load_dotenv

# sys.stdout.reconfigure() doesn't always stick once Streamlit wraps stdout
# on Windows, so this catches the encode failure at the print() call itself —
# guaranteed to work no matter what wraps the stream underneath.
_original_print = builtins.print


def _safe_print(*args, **kwargs):
    try:
        _original_print(*args, **kwargs)
    except UnicodeEncodeError:
        safe_args = [str(a).encode("ascii", errors="replace").decode("ascii") for a in args]
        _original_print(*safe_args, **kwargs)


builtins.print = _safe_print

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

load_dotenv()

# --- API Keys ---
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")  # Fernet key

# --- LLM ---
CEREBRAS_MODEL = "gpt-oss-120b"

# --- Alpha Score Thresholds ---
ALPHA_PPO_THRESHOLD = 70
ALPHA_TALENT_POOL_THRESHOLD = 50
EARLY_OFFBOARD_THRESHOLD = 60  # Week 1 quiz threshold

# --- Pipeline ---
TL_APPROVAL_TIMEOUT_HOURS = 24
SCHEDULER_DAY = "mon"
SCHEDULER_HOUR = 9

# --- Roles ---
ROLES = ["Quant Researcher", "Algo Trader"]

# --- Sourcing ---
DELHI_NCR_LOCATIONS = ["Delhi", "Gurgaon", "Noida", "Faridabad", "Ghaziabad"]
MIN_LEADS = 5

# --- L&D ---
TOTAL_WEEKS = 4
WEAK_TOPIC_THRESHOLD = 60      # below this → topic weighted heavier next week
WEAK_TOPIC_WEIGHT = 0.6        # 60% of next quiz from weak topics
LATERAL_EXPERIENCE_YEARS = 2   # above this → use experience score not institute score

# --- Piston API ---
PISTON_API_URL = "https://emkc.org/api/v2/piston/execute"
CODE_TIMEOUT_SECONDS = 5
CODE_MEMORY_LIMIT_MB = 256

# --- Data Retention (days) ---
FAILED_CANDIDATE_RETENTION_DAYS = 15
OFFBOARDED_RETENTION_DAYS = 60

# --- Streamlit Auth ---
ROLES_AUTH = ["TL", "HR", "Trainee", "Candidate"]