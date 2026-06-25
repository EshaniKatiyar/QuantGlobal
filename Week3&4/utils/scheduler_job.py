from apscheduler.schedulers.background import BackgroundScheduler
import time

_scheduler = None


def trigger_pipeline():
    from supervisors.root import run_pipeline
    print("[Scheduler] Auto-trigger fired — running pipeline")
    try:
        run_pipeline(run_id=int(time.time()))
    except Exception as e:
        print(f"[Scheduler] Pipeline error: {e}")


def start_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        return
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        trigger_pipeline,
        trigger="cron",
        day_of_week="mon",
        hour=9,
        minute=0,
        id="weekly_pipeline"
    )
    _scheduler.start()
    print("[Scheduler] Auto-scheduler started — pipeline runs every Monday at 9:00 AM")


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown()
        print("[Scheduler] Stopped")
        