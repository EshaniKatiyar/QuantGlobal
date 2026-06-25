from database.db import init_db, run_retention_cleanup
from supervisors.root import run_pipeline
import time

if __name__ == "__main__":
    init_db()
    run_id = int(time.time())
    
    # Run the main agentic architecture
    run_pipeline(run_id=run_id)

    # ── THE FIX: Trigger data retention cleanup safely ──
    print("\n[System] Executing automated data retention protocol...")
    try:
        cleaned_count = run_retention_cleanup()
        if cleaned_count and cleaned_count > 0:
            print(f"[System] Success: Purged PII for {cleaned_count} expired candidate records.")
        else:
            print("[System] Retention check complete: No records expired.")
    except Exception as e:
        print(f"[System] Warning: Retention cleanup failed: {e}")