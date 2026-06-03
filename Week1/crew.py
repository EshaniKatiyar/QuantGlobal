from crewai import Crew, Process
from agents import jd_writer, screener, scheduler, onboarding, assessor
from tasks import build_tasks

def run_alphahire(data: dict) -> dict:
    tasks = build_tasks(data)
    crew = Crew(
        agents=[jd_writer, screener, scheduler, onboarding, assessor],
        tasks=tasks,
        process=Process.sequential,
        verbose=False,
    )
    result = crew.kickoff()
    # Extract each task's output
    return {
        "jd":         str(tasks[0].output) if tasks[0].output else "—",
        "screening":  str(tasks[1].output) if tasks[1].output else "—",
        "schedule":   str(tasks[2].output) if tasks[2].output else "—",
        "onboarding": str(tasks[3].output) if tasks[3].output else "—",
        "assessment": str(tasks[4].output) if tasks[4].output else "—",
        "raw":        str(result)
    }