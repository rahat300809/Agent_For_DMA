"""
main.py - Main Entry Point for Punch Reminder AI Agent
Orchestrates DB Query, Memory, Tools, System Prompt, Groq AI, and Console Output.

Usage:
  python3 main.py
  python3 main.py --interactive
  python3 main.py --office-time "10:00 AM" --check-time "10:20 AM" --date "2026-10-04" --limit 5
"""

import sys
import os
import argparse
from datetime import datetime
from db import init_db
from tools import fetch_unpunched_workers, fetch_late_workers, get_latest_attendance_date, is_past_reminder_threshold, is_holiday_date
from memory import AgentMemory, CSV_FILE
from agent import generate_reminder, load_system_prompt

SAFE_TIME_MINUTES = 15

def run_agent(office_time="10:00 AM", check_time="10:20 AM", target_date=None, limit=0, grace_minutes=SAFE_TIME_MINUTES, mode="unpunched"):
    # Ensure DB is initialized
    init_db()

    # Determine target date if not specified
    if not target_date:
        target_date = get_latest_attendance_date()

    # Check Holiday rule
    is_hol, hol_msg = is_holiday_date(target_date)
    if is_hol:
        print("=" * 70)
        print(" 🤖 PUNCH REMINDER AI AGENT - CONSOLE DASHBOARD")
        print("=" * 70)
        print(f" Target Date:        {target_date}")
        print(f" Scheduled Office:   {office_time}")
        print(f" Current Check Time: {check_time}")
        print(f" Mode:               {mode.upper()}")
        print(f" Holiday Check:      {hol_msg}")
        print("=" * 70)
        print(f"\n[🚫 NO MESSAGE GENERATED]")
        print(f"Reason: {hol_msg}")
        print("Reminder messages are strictly disabled on Fridays and configured holidays.")
        print("=" * 70)
        return

    # Check 15-minute safe time rule (only strict if mode is unpunched; for late comers, they are already late, but we can still check it)
    should_send, status_msg = is_past_reminder_threshold(office_time, check_time, grace_minutes=grace_minutes)

    print("=" * 70)
    print(" 🤖 PUNCH REMINDER AI AGENT - CONSOLE DASHBOARD")
    print("=" * 70)
    print(f" Target Date:        {target_date}")
    print(f" Scheduled Office:   {office_time}")
    print(f" Current Check Time: {check_time}")
    print(f" Mode:               {mode.upper()}")
    print(f" Safe Time Rule:     {status_msg}")
    print(f" System Prompt File: system_prompt.txt")
    print(f" CSV Log File:       {os.path.basename(CSV_FILE)}")
    print("=" * 70)

    if not should_send and mode == "unpunched":
        print(f"\n[🚫 NO MESSAGE GENERATED]")
        print(f"Reason: Current check time '{check_time}' is WITHIN 15-min safe time (office {office_time} + {grace_minutes} mins).")
        print("Reminder messages are only triggered when check time is past 15 minutes after office time (past 10:15 AM).")
        print("=" * 70)
        return

    # Initialize Memory & CSV logging
    memory = AgentMemory()

    if mode == "late":
        workers = fetch_late_workers(date_str=target_date, office_time_str=office_time, grace_minutes=grace_minutes)
        if not workers:
            print(f"\n[OK] No late comers found for date {target_date}!")
            return
        print(f"\n[!] Found {len(workers)} late comer(s).")
    else:
        workers = fetch_unpunched_workers(date_str=target_date, office_time_str=office_time)
        if not workers:
            print(f"\n[OK] All active employees have punched in for date {target_date}!")
            return
        print(f"\n[!] Found {len(workers)} worker(s) who haven't punched in yet.")

    if limit and len(workers) > limit:
        print(f"[*] Displaying first {limit} worker reminders (use --limit 0 to display all):\n")
        workers_to_process = workers[:limit]
    else:
        workers_to_process = workers
        print("\n")

    count = 0
    for idx, worker in enumerate(workers_to_process, 1):
        full_name = worker["full_name"]
        phone = worker["phone"]
        user_id = worker["user_id"]

        # Use checkin time if available (for late mode), else check_time
        eff_check_time = worker.get("checkin_time", check_time)

        # Generate AI Reminder message using Groq & system_prompt.txt
        message = generate_reminder(
            employee=worker,
            office_time=office_time,
            check_time=eff_check_time,
            date_str=target_date
        )

        # Log into agent memory AND CSV file
        memory.record_reminder(
            user_id=user_id,
            full_name=full_name,
            phone=phone,
            message=message,
            date_str=target_date,
            office_time=office_time,
            check_time=eff_check_time,
            card_number=worker.get("card_number", "N/A"),
            branch_name=worker.get("branch_name", "Main Office")
        )
        count += 1

        # Display required output in console: Full Name, Phone, and Message
        print("-" * 70)
        print(f" REMINDER #{idx} ({mode.upper()})")
        print(f" FULL NAME : {full_name}")
        print(f" PHONE     : {phone}")
        print(f" MESSAGE   : {message}")
        print("-" * 70)

    print(f"\n[+] Successfully processed, displayed, and logged {count} reminder(s) to '{os.path.basename(CSV_FILE)}'.")
    print("=" * 70)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Punch Reminder AI Agent")
    parser.add_argument("-i", "--interactive", action="store_true", help="Launch interactive manual input menu")
    parser.add_argument("--office-time", type=str, default="10:00 AM", help="Scheduled office start time (e.g. 10:00 AM)")
    parser.add_argument("--check-time", type=str, default="10:20 AM", help="Current check time (e.g. 10:20 AM)")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD (defaults to latest date in DB)")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of reminders displayed in console (0 for all)")
    parser.add_argument("--mode", type=str, choices=["unpunched", "late"], default="unpunched", help="Mode: unpunched or late")

    args = parser.parse_args()

    if args.interactive:
        from manual_input import interactive_menu
        interactive_menu()
    else:
        run_agent(
            office_time=args.office_time,
            check_time=args.check_time,
            target_date=args.date,
            limit=args.limit,
            mode=args.mode
        )

