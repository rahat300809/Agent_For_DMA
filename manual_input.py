"""
manual_input.py - Interactive Manual Input System for Attendance AI Agent

Rules Enforced:
1. DB Cross-Check: Input employee Name or Phone MUST exist in dcard database. If not found, input is REJECTED.
2. 15-Minute Safe Time: Messages are ONLY generated if Check Time > (Office Time + 15 mins).
   Example: Office Time 10:00 AM -> 15-min safe time up to 10:15 AM.
   Check time <= 10:15 AM -> NO message generated.
   Check time > 10:15 AM (e.g. 10:16 AM) -> Message WILL be generated.
3. CSV Logging: All generated reminders are logged into `sent_reminders_log.csv`.
4. Dynamic System Prompt: Prompt can be viewed/edited and is saved to `system_prompt.txt`.

Run with: python3 manual_input.py
"""

import sys
import os
from datetime import datetime
from db import init_db, get_all_attendance_dates, get_connection
from tools import fetch_unpunched_workers, is_past_reminder_threshold, verify_employee_in_db, is_holiday_date
from agent import generate_reminder, load_system_prompt, save_system_prompt, PROMPT_FILE
from memory import AgentMemory, CSV_FILE

SAFE_TIME_MINUTES = 15

def print_banner():
    print("=" * 70)
    print(" 🤖 ATTENDANCE REMINDER AI AGENT - MANUAL INPUT SYSTEM")
    print("=" * 70)

def manual_check_unpunched_workers():
    print("\n--- [Option 1: Check Unpunched Workers from DB] ---")
    available_dates = get_all_attendance_dates()
    default_date = available_dates[0] if available_dates else datetime.now().strftime("%Y-%m-%d")

    print(f"Available recent dates in DB: {', '.join(available_dates[:5])}")
    date_input = input(f"Enter Target Date [YYYY-MM-DD] (Press Enter for '{default_date}'): ").strip()
    if not date_input:
        date_input = default_date

    # STEP 1: Holiday Check
    is_hol, hol_msg = is_holiday_date(date_input)
    if is_hol:
        print("\n" + "=" * 70)
        print(f" 🚫 HOLIDAY DETECTED: {hol_msg}")
        print("=" * 70)
        print(f" Target Date: {date_input}")
        print(" Reason: No reminder messages will be sent or triggered on holidays.")
        print("=" * 70)
        return

    office_time_input = input("Enter Scheduled Office Start Time (Press Enter for '10:00 AM'): ").strip()
    if not office_time_input:
        office_time_input = "10:00 AM"

    check_time_input = input("Enter Current Check Time (Press Enter for '10:20 AM'): ").strip()
    if not check_time_input:
        check_time_input = "10:20 AM"

    # STEP 2: Evaluate 15-minute safe time rule
    should_send, status_msg = is_past_reminder_threshold(office_time_input, check_time_input, grace_minutes=SAFE_TIME_MINUTES)

    print("\n" + "=" * 70)
    print(f" Target Date:        {date_input}")
    print(f" Scheduled Office:   {office_time_input}")
    print(f" Current Check Time: {check_time_input}")
    print(f" Safe Time Rule:     {status_msg}")
    print("=" * 70)

    if not should_send:
        print(f"\n[🚫 NO MESSAGE GENERATED]")
        print(f"Reason: Current check time '{check_time_input}' is WITHIN the {SAFE_TIME_MINUTES}-minute safe time window.")
        print(f"Reminder messages are only triggered when check time passes 15 minutes after office time (past 10:15 AM).")
        return

    limit_input = input("\nHow many reminders to display & log? (Press Enter for '5', or '0' for all): ").strip()
    try:
        limit = int(limit_input) if limit_input else 5
    except ValueError:
        limit = 5

    workers = fetch_unpunched_workers(date_str=date_input, office_time_str=office_time_input)

    if not workers:
        print(f"\n[OK] All workers have punched in for date {date_input}!")
        return

    print(f"\n[!] Found {len(workers)} worker(s) who haven't punched in yet.")
    workers_to_show = workers[:limit] if limit > 0 else workers

    memory = AgentMemory()
    for idx, worker in enumerate(workers_to_show, 1):
        msg = generate_reminder(
            employee=worker,
            office_time=office_time_input,
            check_time=check_time_input,
            date_str=date_input
        )
        memory.record_reminder(
            user_id=worker["user_id"],
            full_name=worker["full_name"],
            phone=worker["phone"],
            message=msg,
            date_str=date_input,
            office_time=office_time_input,
            check_time=check_time_input,
            card_number=worker.get("card_number", "N/A"),
            branch_name=worker.get("branch_name", "Main Office")
        )
        print("-" * 70)
        print(f" REMINDER #{idx}")
        print(f" FULL NAME : {worker['full_name']}")
        print(f" PHONE     : {worker['phone']}")
        print(f" MESSAGE   : {msg}")
        print("-" * 70)

    print(f"\n[+] Successfully generated & logged {len(workers_to_show)} reminder(s) to '{os.path.basename(CSV_FILE)}'.")

def manual_check_late_workers():
    print("\n--- [Option 2: Check Late Comers from DB] ---")
    available_dates = get_all_attendance_dates()
    default_date = available_dates[0] if available_dates else datetime.now().strftime("%Y-%m-%d")

    print(f"Available recent dates in DB: {', '.join(available_dates[:5])}")
    date_input = input(f"Enter Target Date [YYYY-MM-DD] (Press Enter for '{default_date}'): ").strip()
    if not date_input:
        date_input = default_date

    # STEP 1: Holiday Check
    is_hol, hol_msg = is_holiday_date(date_input)
    if is_hol:
        print("\n" + "=" * 70)
        print(f" 🚫 HOLIDAY DETECTED: {hol_msg}")
        print("=" * 70)
        print(f" Target Date: {date_input}")
        print(" Reason: No reminder messages will be sent or triggered on holidays.")
        print("=" * 70)
        return

    office_time_input = input("Enter Scheduled Office Start Time (Press Enter for '10:00 AM'): ").strip()
    if not office_time_input:
        office_time_input = "10:00 AM"

    limit_input = input("\nHow many reminders to display & log? (Press Enter for '5', or '0' for all): ").strip()
    try:
        limit = int(limit_input) if limit_input else 5
    except ValueError:
        limit = 5

    from tools import fetch_late_workers
    workers = fetch_late_workers(date_str=date_input, office_time_str=office_time_input, grace_minutes=SAFE_TIME_MINUTES)

    if not workers:
        print(f"\n[OK] No late comers found for date {date_input} (or no punch data yet)!")
        return

    print(f"\n[!] Found {len(workers)} late comer(s).")
    workers_to_show = workers[:limit] if limit > 0 else workers

    memory = AgentMemory()
    for idx, worker in enumerate(workers_to_show, 1):
        # We don't have a single "current check time" for late comers, they already checked in.
        # But we pass the checkin time as check_time so the prompt makes sense.
        check_time_str = worker["checkin_time"]
        
        msg = generate_reminder(
            employee=worker,
            office_time=office_time_input,
            check_time=check_time_str,
            date_str=date_input
        )
        memory.record_reminder(
            user_id=worker["user_id"],
            full_name=worker["full_name"],
            phone=worker["phone"],
            message=msg,
            date_str=date_input,
            office_time=office_time_input,
            check_time=check_time_str,
            card_number=worker.get("card_number", "N/A"),
            branch_name=worker.get("branch_name", "Main Office")
        )
        print("-" * 70)
        print(f" LATE COMER REMINDER #{idx}")
        print(f" FULL NAME    : {worker['full_name']}")
        print(f" PHONE        : {worker['phone']}")
        print(f" CHECKIN TIME : {check_time_str}")
        print(f" MESSAGE      : {msg}")
        print("-" * 70)

    print(f"\n[+] Successfully generated & logged {len(workers_to_show)} reminder(s) to '{os.path.basename(CSV_FILE)}'.")

def manual_single_employee_test():
    print("\n--- [Option 2: Test Employee DB Cross-Check & Manual Input] ---")
    print(" (Refer to db_sample_employees.txt for registered names/phones)")
    input_query = input("Enter Employee Name or Phone Number to verify in dcard DB: ").strip()

    if not input_query:
        print("[!] Input query cannot be empty.")
        return

    # STEP 1: DB Cross-Check
    emp_db = verify_employee_in_db(input_query)

    if not emp_db:
        print("\n" + "=" * 70)
        print(f" ❌ INPUT REJECTED: '{input_query}' NOT FOUND IN dcard DATABASE!")
        print("=" * 70)
        print(" Reason: The input Name or Phone does not match any registered user in dcard DB.")
        print(" Please check db_sample_employees.txt for a list of valid registered employees.")
        print("=" * 70)
        return

    print("\n[✓] DB CROSS-CHECK SUCCESSFUL!")
    print(f"     Matched Employee ID : {emp_db['user_id']}")
    print(f"     Full Name           : {emp_db['full_name']}")
    print(f"     Registered Phone    : {emp_db['phone']}")
    print(f"     Card Number         : {emp_db['card_number']}")
    print(f"     Branch              : {emp_db['branch_name']}")

    # Manual Target Date Input
    default_date = datetime.now().strftime("%Y-%m-%d")
    date_input = input(f"\nEnter Target Date [YYYY-MM-DD] (Press Enter for today '{default_date}'): ").strip()
    if not date_input:
        date_input = default_date

    # STEP 2: Holiday Check
    is_hol, hol_msg = is_holiday_date(date_input)
    if is_hol:
        print("\n" + "=" * 70)
        print(f" 🚫 HOLIDAY DETECTED: {hol_msg}")
        print("=" * 70)
        print(f" FULL NAME : {emp_db['full_name']}")
        print(f" PHONE     : {emp_db['phone']}")
        print(f" DATE      : {date_input}")
        print(" STATUS    : NO REMINDER MESSAGES ARE SENT OR TRIGGERED ON HOLIDAYS.")
        print("=" * 70)
        return

    office_time = input("Enter Scheduled Office Start Time (Press Enter for '10:00 AM'): ").strip()
    if not office_time:
        office_time = "10:00 AM"

    check_time = input("Enter Current Check Time (e.g. '10:10 AM' vs '10:20 AM'): ").strip()
    if not check_time:
        check_time = "10:20 AM"

    # STEP 3: 15-Minute Safe Time Check
    should_send, status_msg = is_past_reminder_threshold(office_time, check_time, grace_minutes=SAFE_TIME_MINUTES)

    print("\n" + "=" * 70)
    print(f" 15-MIN SAFE TIME EVALUATION: {status_msg}")
    print("=" * 70)

    if not should_send:
        print(f"\n[🚫 NO MESSAGE GENERATED]")
        print(f" FULL NAME : {emp_db['full_name']}")
        print(f" PHONE     : {emp_db['phone']}")
        print(f" REASON    : Check time '{check_time}' is WITHIN 15-min safe time (up to 10:15 AM). No message sent.")
        print("=" * 70)
        return

    print("\n[AI] Safe time crossed! Generating customized AI reminder using Groq API...")
    msg = generate_reminder(
        employee=emp_db,
        office_time=office_time,
        check_time=check_time,
        date_str=date_input
    )

    # Log into Memory & CSV
    memory = AgentMemory()
    memory.record_reminder(
        user_id=emp_db["user_id"],
        full_name=emp_db["full_name"],
        phone=emp_db["phone"],
        message=msg,
        date_str=date_input,
        office_time=office_time,
        check_time=check_time,
        card_number=emp_db["card_number"],
        branch_name=emp_db["branch_name"]
    )

    print("\n" + "=" * 70)
    print(" RESULT OUTPUT:")
    print("=" * 70)
    print(f" FULL NAME : {emp_db['full_name']}")
    print(f" PHONE     : {emp_db['phone']}")
    print(f" MESSAGE   : {msg}")
    print("=" * 70)
    print(f"[+] Record saved to '{os.path.basename(CSV_FILE)}'")

def search_db_employee():
    print("\n--- [Option 3: Search Employee in Database] ---")
    search_query = input("Enter name or phone to search in dcard DB: ").strip()
    if not search_query:
        print("[!] Empty search query.")
        return

    emp_db = verify_employee_in_db(search_query)
    if not emp_db:
        print(f"\n[❌ NOT FOUND] No employee matching '{search_query}' in dcard DB.")
        return

    print(f"\n[✓] Found: {emp_db['full_name']} | Phone: {emp_db['phone']} | Branch: {emp_db['branch_name']}")

    default_date = datetime.now().strftime("%Y-%m-%d")
    date_input = input(f"Enter Target Date [YYYY-MM-DD] (Press Enter for today '{default_date}'): ").strip()
    if not date_input:
        date_input = default_date

    # Holiday Check
    is_hol, hol_msg = is_holiday_date(date_input)
    if is_hol:
        print("\n" + "=" * 70)
        print(f" 🚫 HOLIDAY DETECTED: {hol_msg}")
        print("=" * 70)
        print(f" FULL NAME : {emp_db['full_name']}")
        print(f" PHONE     : {emp_db['phone']}")
        print(f" DATE      : {date_input}")
        print(" STATUS    : NO REMINDER MESSAGES ARE SENT OR TRIGGERED ON HOLIDAYS.")
        print("=" * 70)
        return

    office_time = input("Enter Scheduled Office Time (default '10:00 AM'): ").strip() or "10:00 AM"
    check_time = input("Enter Current Check Time (default '10:20 AM'): ").strip() or "10:20 AM"

    should_send, status_msg = is_past_reminder_threshold(office_time, check_time, grace_minutes=SAFE_TIME_MINUTES)
    print("\n" + "=" * 70)
    print(f" SAFE TIME EVALUATION: {status_msg}")
    print("=" * 70)

    if not should_send:
        print(f"\n[🚫 NO MESSAGE GENERATED]")
        print(f"FULL NAME : {emp_db['full_name']}")
        print(f"PHONE     : {emp_db['phone']}")
        print(f"STATUS    : Time '{check_time}' is within 15-min safe time. No reminder sent.")
        print("=" * 70)
        return

    msg = generate_reminder(emp_db, office_time=office_time, check_time=check_time, date_str=date_input)

    # Log to CSV
    memory = AgentMemory()
    memory.record_reminder(
        user_id=emp_db["user_id"],
        full_name=emp_db["full_name"],
        phone=emp_db["phone"],
        message=msg,
        date_str=date_input,
        office_time=office_time,
        check_time=check_time,
        card_number=emp_db["card_number"],
        branch_name=emp_db["branch_name"]
    )

    print("\n" + "=" * 70)
    print(f" FULL NAME : {emp_db['full_name']}")
    print(f" PHONE     : {emp_db['phone']}")
    print(f" MESSAGE   : {msg}")
    print("=" * 70)
    print(f"[+] Record saved to '{os.path.basename(CSV_FILE)}'")


def edit_system_prompt():
    print("\n--- [Option 4: View / Edit System Prompt Template] ---")
    current_prompt = load_system_prompt()
    print("Current System Prompt:")
    print("-" * 50)
    print(current_prompt)
    print("-" * 50)

    change = input("Do you want to update the system prompt? (y/n): ").strip().lower()
    if change == 'y':
        print("\nEnter new system prompt text (Type 'END' on a new line when finished):")
        lines = []
        while True:
            line = input()
            if line.strip() == "END":
                break
            lines.append(line)
        new_prompt = "\n".join(lines).strip()
        if new_prompt:
            save_system_prompt(new_prompt)
            print("[✓] System prompt updated and saved successfully!")
        else:
            print("[!] Prompt cannot be empty. Update cancelled.")

def interactive_menu():
    init_db()
    while True:
        print_banner()
        print(" 1. 📅 Check Unpunched Workers by Date & Time (DB Query)")
        print(" 2. ⏰ Check Late Comers by Date & Time (DB Query)")
        print(" 3. 👤 Manual Input Test with DB Cross-Check & 15-min Safe Time")
        print(" 4. 🔍 Search Employee in Database & Generate Reminder")
        print(" 5. ✏️  View / Edit System Prompt (system_prompt.txt)")
        print(" 6. 🚪 Exit")
        print("=" * 70)

        choice = input("Select an option (1-6): ").strip()

        if choice == "1":
            manual_check_unpunched_workers()
        elif choice == "2":
            manual_check_late_workers()
        elif choice == "3":
            manual_single_employee_test()
        elif choice == "4":
            search_db_employee()
        elif choice == "5":
            edit_system_prompt()
        elif choice == "6":
            print("\nExiting Manual Input System. Goodbye! 👋")
            sys.exit(0)
        else:
            print("\n[!] Invalid selection. Please choose 1, 2, 3, 4, 5, or 6.")

        input("\nPress Enter to return to the main menu...")

if __name__ == "__main__":
    interactive_menu()
