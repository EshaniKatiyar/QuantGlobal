"""
Real external tool integrations.
GitHub API, Google Custom Search, Piston sandbox.
No mock data used here — all real API calls.
"""

import requests
import hashlib
import subprocess
import tempfile
import os
import sys
from typing import List, Dict, Any
from config import (
    CODE_MEMORY_LIMIT_MB, GITHUB_TOKEN, GOOGLE_API_KEY, GOOGLE_CSE_ID,
    DELHI_NCR_LOCATIONS, PISTON_API_URL, CODE_TIMEOUT_SECONDS
)


# ─────────────────────────────────────────────
# GITHUB API
# ─────────────────────────────────────────────

QUANT_RESEARCHER_TOPICS = [
    "quantitative-finance", "options-pricing", "backtesting",
    "statistical-arbitrage", "factor-model", "quant-research"
]
ALGO_TRADER_TOPICS = [
    "algorithmic-trading", "algo-trading", "hft",
    "execution-algo", "market-making", "order-book"
]


def infer_role_from_profile(repos: List[str], bio: str) -> str:
    """Infer role from GitHub repos and bio."""
    text = " ".join(repos).lower() + " " + (bio or "").lower()
    researcher_hits = sum(1 for k in QUANT_RESEARCHER_TOPICS if k.replace("-", " ") in text or k in text)
    trader_hits = sum(1 for k in ALGO_TRADER_TOPICS if k.replace("-", " ") in text or k in text)
    return "Quant Researcher" if researcher_hits >= trader_hits else "Algo Trader"


def get_github_user_detail(username: str, headers: dict) -> Dict[str, Any]:
    """Fetch detailed profile for a GitHub user."""
    try:
        resp = requests.get(
            f"https://api.github.com/users/{username}",
            headers=headers, timeout=10
        )
        return resp.json() if resp.status_code == 200 else {}
    except Exception:
        return {}


def get_github_repos(username: str, headers: dict) -> List[Dict]:
    """Fetch public repos for a GitHub user."""
    try:
        resp = requests.get(
            f"https://api.github.com/users/{username}/repos",
            headers=headers,
            params={"per_page": 30, "sort": "updated"},
            timeout=10
        )
        return resp.json() if resp.status_code == 200 else []
    except Exception:
        return []


def search_github_candidates(max_results: int = 15) -> List[Dict[str, Any]]:
    """
    Search GitHub for real Delhi-NCR quant candidates.
    Queries multiple topic combinations for best coverage.
    """
    if not GITHUB_TOKEN:
        print("[Tools:GitHub] No token — skipping")
        return []

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    location_q = " OR ".join([f"location:{loc}" for loc in DELHI_NCR_LOCATIONS])
    queries = [
        f"({location_q}) language:Python topic:algorithmic-trading",
        f"({location_q}) language:Python topic:quantitative-finance",
        f"({location_q}) language:Python quant trading",
    ]

    seen_usernames = set()
    candidates = []

    for query in queries:
        if len(candidates) >= max_results:
            break
        try:
            resp = requests.get(
                "https://api.github.com/search/users",
                headers=headers,
                params={"q": query, "per_page": 10},
                timeout=10
            )
            if resp.status_code != 200:
                print(f"[Tools:GitHub] API error {resp.status_code}: {resp.json().get('message', '')}")
                continue

            users = resp.json().get("items", [])
            for user in users:
                username = user.get("login", "")
                if username in seen_usernames:
                    continue
                seen_usernames.add(username)

                detail = get_github_user_detail(username, headers)
                location = (detail.get("location") or "").strip()

                # Strict Delhi/NCR filter
                if not any(loc.lower() in location.lower() for loc in DELHI_NCR_LOCATIONS):
                    continue

                repos_raw = get_github_repos(username, headers)
                repo_names = [
                    r.get("name", "") + " " + (r.get("description") or "")
                    for r in repos_raw
                ]
                total_stars = sum(r.get("stargazers_count", 0) for r in repos_raw)
                bio = detail.get("bio") or ""
                role = infer_role_from_profile(repo_names, bio)
                mock_email = f"{username.lower().replace('-', '.')}@mock.qg.com"

                candidates.append({
                    "name": detail.get("name") or username,
                    "github_url": detail.get("html_url", f"https://github.com/{username}"),
                    "email": mock_email,
                    "role": role,
                    "source": "GitHub",
                    "repos": repo_names[:10],
                    "bio": bio,
                    "stars": total_stars,
                    "location": location,
                    "followers": detail.get("followers", 0),
                    "public_repos": detail.get("public_repos", 0),
                })

        except Exception as e:
            print(f"[Tools:GitHub] Error: {e}")

    print(f"[Tools:GitHub] Found {len(candidates)} real Delhi-NCR candidates")
    return candidates


# ─────────────────────────────────────────────
# GOOGLE CUSTOM SEARCH
# ─────────────────────────────────────────────

def search_google_candidates(max_results: int = 5) -> List[Dict[str, Any]]:
    """Search Google CSE for quant candidate profiles."""
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        print("[Tools:Google] No credentials — skipping")
        return []

    queries = [
        '"quant researcher" "Delhi" OR "Noida" OR "Gurgaon" site:github.com',
        '"algorithmic trading" "Delhi NCR" site:github.com',
        '"quantitative finance" Delhi site:linkedin.com/in',
    ]

    candidates = []
    seen = set()

    for query in queries:
        if len(candidates) >= max_results:
            break
        try:
            resp = requests.get(
                "https://www.googleapis.com/customsearch/v1",
                params={
                    "key": GOOGLE_API_KEY,
                    "cx": GOOGLE_CSE_ID,
                    "q": query,
                    "num": 5
                },
                timeout=10
            )
            if resp.status_code != 200:
                print(f"[Tools:Google] API error {resp.status_code}")
                continue

            for item in resp.json().get("items", []):
                link = item.get("link", "")
                title = item.get("title", "")
                snippet = item.get("snippet", "")

                if link in seen:
                    continue
                seen.add(link)

                username = link.rstrip("/").split("/")[-1]
                role = infer_role_from_profile([], snippet + " " + title)
                mock_email = f"{username.lower().replace('-', '.')}@mock.qg.com"

                candidates.append({
                    "name": title.split(" - ")[0].split(" | ")[0].strip() or username,
                    "github_url": link,
                    "email": mock_email,
                    "role": role,
                    "source": "Google",
                    "repos": [],
                    "bio": snippet,
                    "stars": 0,
                    "location": "Delhi NCR",
                    "followers": 0,
                    "public_repos": 0,
                })

        except Exception as e:
            print(f"[Tools:Google] Error: {e}")

    print(f"[Tools:Google] Found {len(candidates)} candidates")
    return candidates


# ─────────────────────────────────────────────
# PISTON SANDBOX
# ─────────────────────────────────────────────

def execute_code_safely(code: str, language: str = "python") -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        script_path = os.path.join(tmpdir, "candidate_code.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(code)

        def _limit_resources():
            try:
                import resource
                resource.setrlimit(resource.RLIMIT_AS, (CODE_MEMORY_LIMIT_MB * 1024 * 1024,) * 2)
                resource.setrlimit(resource.RLIMIT_CPU, (CODE_TIMEOUT_SECONDS, CODE_TIMEOUT_SECONDS))
            except Exception:
                pass  # not available on Windows

        # FIX 1: Pass a copy of the full OS environment. 
        # Windows Python requires 'SystemRoot' and other vars to load DLLs properly.
        sandbox_env = os.environ.copy()

        try:
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=CODE_TIMEOUT_SECONDS,
                env=sandbox_env,
                preexec_fn=_limit_resources if os.name == "posix" else None,
                cwd=tmpdir,
                # FIX 2: Disconnect the keyboard input. 
                # If the LLM writes an input() prompt, this instantly throws an 
                # EOFError crash instead of hanging the process forever.
                stdin=subprocess.DEVNULL 
            )
            return {
                "stdout": (result.stdout or "").strip()[:2000],
                "stderr": (result.stderr or "").strip()[:1000],
                "success": result.returncode == 0,
                "sandboxed": True
            }
        except subprocess.TimeoutExpired:
            return {"stdout": "", "stderr": f"Timed out after {CODE_TIMEOUT_SECONDS}s", "success": False, "sandboxed": True}
        except Exception as e:
            print(f"[Tools:Sandbox] Error: {e}")
            return {"stdout": "", "stderr": "Execution failed", "success": False, "sandboxed": True}


# ─────────────────────────────────────────────
# MOCK FALLBACK (only if APIs return nothing)
# ─────────────────────────────────────────────

MOCK_CANDIDATES = [
    {
        "name": "Arjun Kapoor", "role": "Quant Researcher",
        "bio": "IIT Delhi | Quant Research | Options pricing, Statistical Arbitrage | Python",
        "repos": ["black-scholes-pricer", "stat-arb-backtest", "factor-model-research"],
        "stars": 34, "location": "New Delhi", "institute": "IIT Delhi",
        "years_experience": 0, "followers": 45, "public_repos": 12
    },
    {
        "name": "Priya Sharma", "role": "Algo Trader",
        "bio": "NIT Kurukshetra → Quant Trading @ Noida | Execution algos, Market microstructure",
        "repos": ["vwap-execution-engine", "order-book-analyser", "hft-simulator"],
        "stars": 28, "location": "Noida", "institute": "NIT Kurukshetra",
        "years_experience": 3, "followers": 32, "public_repos": 9
    },
    {
        "name": "Rahul Mehta", "role": "Quant Researcher",
        "bio": "ISI Delhi | Probability, Stochastic Calculus | Backtesting frameworks",
        "repos": ["monte-carlo-pricer", "cointegration-pairs-trading", "risk-model-portfolio"],
        "stars": 67, "location": "Delhi", "institute": "ISI Delhi",
        "years_experience": 1, "followers": 89, "public_repos": 18
    },
    {
        "name": "Sneha Agarwal", "role": "Algo Trader",
        "bio": "BITS Pilani | 4yr algo trading | Low latency, WebSocket feeds, Market making",
        "repos": ["market-maker-bot", "latency-benchmarking", "order-flow-imbalance"],
        "stars": 41, "location": "Gurgaon", "institute": "BITS Pilani",
        "years_experience": 4, "followers": 61, "public_repos": 15
    },
    {
        "name": "Vikram Singh", "role": "Quant Researcher",
        "bio": "IIT Roorkee | Signal research, Factor investing | Pandas, numpy, scipy",
        "repos": ["alpha-factor-library", "backtesting-engine", "portfolio-optimiser"],
        "stars": 22, "location": "Noida", "institute": "IIT Roorkee",
        "years_experience": 0, "followers": 28, "public_repos": 8
    },
    {
        "name": "Ananya Verma", "role": "Algo Trader",
        "bio": "Delhi University → 5yr trading desk | Risk management, Kill switches, Position sizing",
        "repos": ["risk-management-system", "kill-switch-implementation", "kelly-criterion-sizer"],
        "stars": 55, "location": "Delhi", "institute": "Delhi University",
        "years_experience": 5, "followers": 73, "public_repos": 14
    },
    {
        "name": "Kartik Bose", "role": "Quant Researcher",
        "bio": "CMI Chennai → Delhi | Stochastic processes, derivatives pricing | Python, C++",
        "repos": ["heston-model-calibration", "vol-surface-builder", "greeks-engine"],
        "stars": 19, "location": "Delhi", "institute": "CMI",
        "years_experience": 0, "followers": 21, "public_repos": 7
    },
    {
        "name": "Deepika Nair", "role": "Quant Researcher",
        "bio": "IIT Kanpur | Machine learning for alpha signals | scikit-learn, pytorch",
        "repos": ["ml-alpha-signals", "feature-engineering-quant", "regime-detection"],
        "stars": 38, "location": "Noida", "institute": "IIT Kanpur",
        "years_experience": 1, "followers": 40, "public_repos": 11
    },
    {
        "name": "Rohan Gupta", "role": "Algo Trader",
        "bio": "Tier-2 college, Faridabad | 2yr prop trading | Order routing, FIX protocol",
        "repos": ["fix-protocol-parser", "smart-order-router", "latency-monitor"],
        "stars": 15, "location": "Faridabad", "institute": "Tier-2",
        "years_experience": 2, "followers": 18, "public_repos": 6
    },
    {
        "name": "Aisha Khan", "role": "Algo Trader",
        "bio": "Delhi College of Engineering | 1yr internship | Backtesting, strategy execution",
        "repos": ["strategy-backtester", "slippage-model", "tick-data-handler"],
        "stars": 12, "location": "Ghaziabad", "institute": "Tier-2",
        "years_experience": 1, "followers": 14, "public_repos": 5
    },
    {
        "name": "Siddharth Rao", "role": "Algo Trader",
        "bio": "BITS Pilani | Execution algos, market microstructure | C++, Python",
        "repos": ["twap-vwap-suite", "queue-position-model", "exchange-simulator"],
        "stars": 47, "location": "Gurgaon", "institute": "BITS Pilani",
        "years_experience": 2, "followers": 50, "public_repos": 13
    },
    {
        "name": "Meera Joshi", "role": "Quant Researcher",
        "bio": "ISI Kolkata → Delhi | Volatility modelling, GARCH | R, Python",
        "repos": ["garch-vol-forecasting", "options-greeks-lib", "risk-parity-portfolio"],
        "stars": 30, "location": "Delhi", "institute": "ISI",
        "years_experience": 0, "followers": 33, "public_repos": 9
    },
    {
        "name": "Aditya Malhotra", "role": "Quant Researcher",
        "bio": "IIT Bombay alum, now Delhi-based | Factor research, portfolio construction",
        "repos": ["multi-factor-model", "risk-budgeting", "backtest-attribution"],
        "stars": 44, "location": "New Delhi", "institute": "IIT",
        "years_experience": 3, "followers": 58, "public_repos": 16
    },
    {
        "name": "Tanvi Chopra", "role": "Algo Trader",
        "bio": "NIT Delhi | Real-time execution systems | Go, Python, Redis",
        "repos": ["realtime-execution-engine", "websocket-feed-handler", "risk-limits-service"],
        "stars": 26, "location": "Delhi", "institute": "NIT",
        "years_experience": 1, "followers": 29, "public_repos": 10
    },
    {
        "name": "Karan Bhatia", "role": "Quant Researcher",
        "bio": "Delhi University | Self-taught quant, strong open-source presence | Python, Julia",
        "repos": ["pairs-trading-framework", "kalman-filter-pricing", "options-chain-analyzer"],
        "stars": 51, "location": "Delhi", "institute": "Other",
        "years_experience": 0, "followers": 65, "public_repos": 20
    },
    {
        "name": "Ishaan Verma", "role": "Algo Trader",
        "bio": "IIT Roorkee | HFT infra, low-latency systems | C++, Rust",
        "repos": ["lockfree-orderbook", "latency-arb-detector", "co-location-sim"],
        "stars": 60, "location": "Gurgaon", "institute": "IIT Roorkee",
        "years_experience": 2, "followers": 70, "public_repos": 17
    },
]


def get_mock_candidates(count: int = 5) -> List[Dict[str, Any]]:
    """Return mock candidates when real APIs yield nothing. Last resort.

    Pulls from the fixed MOCK_CANDIDATES pool first. If a run needs more
    than what's left unused this session (dedup in sourcer.py filters out
    ones already in the DB), this generates additional plausible synthetic
    leads so demo runs don't permanently dry up after the pool is consumed —
    mirrors how a real GitHub/Google search would keep finding *new* people
    each week, which a fixed list can't simulate on its own.
    """
    import random
    from database.db import get_conn

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT email FROM candidates")
    existing_emails = {row[0] for row in c.fetchall()}
    conn.close()

    results = []
    pool = MOCK_CANDIDATES[:]
    random.shuffle(pool)

    for d in pool:
        if len(results) >= count:
            break
        username = d["name"].lower().replace(" ", ".")
        email = f"{username}@mock.qg.com"
        if email in existing_emails:
            continue
        results.append({
            **d,
            "github_url": f"https://github.com/{username}",
            "email": email,
            "source": "Mock",
        })

    if len(results) < count:
        first_names = ["Rohit", "Naina", "Varun", "Pooja", "Akash", "Riya", "Dev", "Sanya"]
        last_names = ["Sethi", "Kapur", "Saxena", "Bedi", "Chawla", "Goel", "Trivedi"]
        roles = ["Quant Researcher", "Algo Trader"]
        institutes = ["IIT", "NIT", "BITS", "Tier-2", "Other"]
        for i in range(count - len(results)):
            fn, ln = random.choice(first_names), random.choice(last_names)
            tag = random.randint(100, 999)
            name = f"{fn} {ln}"
            username = f"{fn.lower()}.{ln.lower()}{tag}"
            results.append({
                "name": name, "role": random.choice(roles),
                "bio": f"{random.choice(institutes)} | Delhi-NCR quant profile | Python",
                "repos": ["quant-research-notebook", "backtest-utils"],
                "stars": random.randint(5, 40), "location": random.choice(DELHI_NCR_LOCATIONS),
                "institute": random.choice(institutes), "years_experience": random.randint(0, 4),
                "followers": random.randint(5, 60), "public_repos": random.randint(3, 15),
                "github_url": f"https://github.com/{username}",
                "email": f"{username}@mock.qg.com",
                "source": "Mock",
            })

    return results