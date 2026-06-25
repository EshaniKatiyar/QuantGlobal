from config import LATERAL_EXPERIENCE_YEARS


INSTITUTE_SCORES = {
    "IIT": 25, "ISI": 25, "CMI": 25,
    "NIT": 15, "BITS": 15,
    "Tier-2": 15, "Other": 5
}


def compute_github_signal(repos: list, commit_frequency: float, stars: int) -> float:
    """Score 0-25 based on GitHub activity quality."""
    score = 0

    # Repo relevance
    quant_keywords = ["quant", "algo", "trading", "finance", "backtest", "arbitrage", "options", "risk"]
    relevant = sum(1 for r in repos if any(k in r.lower() for k in quant_keywords))
    score += min(relevant * 3, 12)

    # Commit frequency (commits/week)
    if commit_frequency >= 5:
        score += 8
    elif commit_frequency >= 2:
        score += 5
    elif commit_frequency >= 1:
        score += 2

    # Stars as credibility signal
    if stars >= 50:
        score += 5
    elif stars >= 10:
        score += 3
    elif stars >= 1:
        score += 1

    return min(score, 25)


def compute_background_fit(institute: str, years_experience: float) -> float:
    """Score 0-25. For laterals (>2yr exp), use experience score instead of institute."""
    if years_experience >= LATERAL_EXPERIENCE_YEARS:
        # Experience-based scoring for laterals
        if years_experience >= 5:
            return 25
        elif years_experience >= 3:
            return 18
        else:
            return 12
    else:
        # Institute-based scoring for freshers
        for key, val in INSTITUTE_SCORES.items():
            if key.lower() in institute.lower():
                return val
        return 5


def compute_assessment_score(correct: int, total: int, time_taken_mins: float, max_time_mins: float) -> float:
    """Score 0-25 based on accuracy + speed."""
    accuracy = (correct / total) * 18 if total > 0 else 0
    speed_bonus = max(0, (1 - time_taken_mins / max_time_mins)) * 7
    return min(accuracy + speed_bonus, 25)


def compute_alpha_v1(github_signal: float, background_fit: float, assessment_score: float) -> float:
    """Alpha Score v1: 0-75. Post screening."""
    return round(github_signal + background_fit + assessment_score, 2)


def compute_learning_velocity(weekly_scores: list) -> float:
    """Score 0-25. Rewards improving trajectory across 4 weeks."""
    if len(weekly_scores) < 2:
        return weekly_scores[0] * 0.25 if weekly_scores else 0

    # Calculate trend: are scores improving?
    improvements = sum(
        1 for i in range(1, len(weekly_scores))
        if weekly_scores[i] > weekly_scores[i - 1]
    )
    trend_bonus = (improvements / (len(weekly_scores) - 1)) * 10

    # Final week score matters most
    final_score = weekly_scores[-1] * 0.15

    return min(round(trend_bonus + final_score, 2), 25)


def compute_alpha_v2(alpha_v1: float, weekly_scores: list) -> float:
    """Alpha Score v2: 0-100. Final post-L&D score."""
    learning_velocity = compute_learning_velocity(weekly_scores)
    return round(alpha_v1 + learning_velocity, 2)


def get_decision(alpha_v2: float) -> str:
    """Map final Alpha Score to decision."""
    if alpha_v2 >= 70:
        return "PPO"
    elif alpha_v2 >= 50:
        return "Talent Pool"
    else:
        return "Offboard"