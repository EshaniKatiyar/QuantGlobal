from crewai import Agent
from config import get_llm

llm = get_llm()
_base = dict(llm=llm, verbose=False, max_iter=3, max_rpm=3)
# max_iter=2 is critical for 3b model — prevents infinite retry loops

jd_writer = Agent(
    role="JD Writer",
    goal="Write a precise Quant Researcher job description in exactly 5 bullet points.",
    backstory="Senior HR specialist at a Delhi-NCR quant fund. Writes JDs used by top IIT/IIM grads.",
    **_base
)

screener = Agent(
    role="Candidate Screener",
    goal="Score each candidate 0-100 against the role requirements. Return a ranked list.",
    backstory="Quant hiring manager. Scores candidates purely on skills, experience, GPA fit.",
    **_base
)

scheduler = Agent(
    role="Interview Scheduler",
    goal="Assign interview slots to top 3 candidates. Output a clean schedule table.",
    backstory="Ops coordinator for a quant trading firm. Runs a tight, no-overlap schedule.",
    **_base
)

onboarding = Agent(
    role="Onboarding Agent",
    goal="Generate a 30-day onboarding plan for the top-ranked candidate. Use 3 phases.",
    backstory="L&D specialist at an algo trading firm. Designs structured quant onboarding programs.",
    **_base
)

assessor = Agent(
    role="Assessment Designer",
    goal="Create exactly 3 quant aptitude questions for the screening round. Include answer keys.",
    backstory="Quant with 10 years experience. Designs problem sets that test real trading intuition.",
    **_base
)