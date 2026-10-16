"""
run_all.py - Convenient entry point script to run the full Attendance Reminder Agent pipeline.
"""

from main import run_agent

if __name__ == "__main__":
    print("[RUN ALL] Launching Punch Reminder Agent Pipeline for Unpunched Workers...")
    run_agent(office_time="10:00 AM", check_time="10:20 AM", limit=0, mode="unpunched")

    print("\n[RUN ALL] Launching Punch Reminder Agent Pipeline for Late Comers...")
    run_agent(office_time="10:00 AM", check_time="10:20 AM", limit=0, mode="late")

