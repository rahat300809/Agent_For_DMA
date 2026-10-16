"""
tools.py - DB Query Tools & Time Validation for Attendance Agent
Can be run individually: python3 tools.py
"""

from datetime import datetime
from db import query_unpunched_employees, get_all_attendance_dates, get_connection

def is_holiday_date(date_str, system_prompt_text=None):
    """
    Checks if a given date_str is a holiday (Friday weekly holiday or dates specified in system prompt / common holidays like 16 Dec).
    Returns (is_holiday: bool, reason_message: str).
    """
    if not date_str:
        return False, "No date provided"
    
    date_str_clean = date_str.strip()
    
    # Try parsing date
    dt = None
    for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y", "%d %b %Y", "%d %B %Y", "%d %b", "%d %B"]:
        try:
            dt = datetime.strptime(date_str_clean, fmt)
            break
        except ValueError:
            pass

    # 1. Friday Check (Friday is weekday index 4 in Python: Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6)
    if dt and dt.weekday() == 4:
        day_name = dt.strftime("%A")
        return True, f"Target Date '{date_str_clean}' is {day_name} (Weekly Holiday). No reminder message will be sent."

    # Load system prompt text if not passed
    if system_prompt_text is None:
        try:
            from agent import load_system_prompt
            system_prompt_text = load_system_prompt()
        except Exception:
            system_prompt_text = ""

    prompt_lower = (system_prompt_text or "").lower()

    # 2. Check date strings against prompt text & common national holidays
    if dt:
        day_num = dt.day
        month_name_short = dt.strftime("%b").lower()
        month_name_full = dt.strftime("%B").lower()
        formatted_1 = f"{day_num} {month_name_short}"
        formatted_2 = f"{day_num} {month_name_full}"
        formatted_iso = dt.strftime("%Y-%m-%d")
        formatted_day_month = f"{day_num:02d}-{dt.month:02d}"

        # Check if prompt explicitly mentions holiday date
        if (formatted_1 in prompt_lower or 
            formatted_2 in prompt_lower or 
            formatted_iso in prompt_lower or 
            formatted_day_month in prompt_lower):
            return True, f"Target Date '{date_str_clean}' ({dt.strftime('%d %B')}) is configured as a Holiday in system prompt. No reminder message will be sent."

        # Standard national holidays (16 Dec = Victory Day, 21 Feb = Language Day, 26 Mar = Independence Day, 1 May = May Day)
        national_holidays = {
            (16, 12): "Victory Day (16 Dec)",
            (21, 2): "Language Movement Day (21 Feb)",
            (26, 3): "Independence Day (26 Mar)",
            (1, 5): "May Day (1 May)"
        }
        if (dt.day, dt.month) in national_holidays:
            h_name = national_holidays[(dt.day, dt.month)]
            return True, f"Target Date '{date_str_clean}' is a National Holiday ({h_name}). No reminder message will be sent."
    else:
        if "friday" in date_str_clean.lower() or "16 dec" in date_str_clean.lower():
            return True, f"Target Date '{date_str_clean}' is recognized as a Holiday. No reminder message will be sent."

    return False, "Not a holiday"


def parse_time(time_str):
    """
    Parses various time string formats into a datetime.time object.
    """
    if not time_str:
        return None
    time_str = time_str.strip().upper()
    formats = ['%I:%M %p', '%I:%M%p', '%H:%M:%S.%f', '%H:%M:%S', '%H:%M']
    for fmt in formats:
        try:
            return datetime.strptime(time_str, fmt).time()
        except ValueError:
            pass
    return None

def is_past_reminder_threshold(office_time_str, check_time_str, grace_minutes=15):
    """
    Returns True if check_time_str has passed the office_time_str + 15 mins (safe time).
    Example: Office Time 10:00 AM, 15 min safe time -> Threshold is 10:15 AM.
    If Check Time <= 10:15 AM -> returns False (Do NOT send message).
    If Check Time > 10:15 AM (e.g. 10:16 AM) -> returns True (SEND message).
    """
    t_off = parse_time(office_time_str)
    t_chk = parse_time(check_time_str)

    if not t_off or not t_chk:
        return True, "Invalid time format (proceeding by default)"

    m_off = t_off.hour * 60 + t_off.minute
    m_chk = t_chk.hour * 60 + t_chk.minute
    m_thresh = m_off + grace_minutes

    thresh_hour = (m_thresh // 60) % 24
    thresh_min = m_thresh % 60
    am_pm = "AM" if thresh_hour < 12 else "PM"
    display_hour = thresh_hour % 12
    if display_hour == 0:
        display_hour = 12
    thresh_str = f"{display_hour:02d}:{thresh_min:02d} {am_pm}"

    if m_chk > m_thresh:
        return True, f"Check time ({check_time_str}) is PAST 15-min safe time ({thresh_str}). Message WILL be generated."
    else:
        return False, f"Check time ({check_time_str}) is WITHIN 15-min safe time (up to {thresh_str}). Message WILL NOT be generated."

def verify_employee_in_db(name_or_phone):
    """
    Cross-checks if an employee name or phone number exists in dcard database.
    Returns employee dict if found, or None if not found.
    """
    if not name_or_phone:
        return None

    term = name_or_phone.strip()
    conn = get_connection()
    cursor = conn.cursor()

    # Clean phone numbers for flexible search (e.g., matching '01718507822' or '1718507822')
    clean_term = re.sub(r'\D', '', term)
    phone_query = f"%{clean_term}%" if clean_term else f"%{term}%"

    sql = """
    SELECT 
        u.id AS user_id,
        u.first_name,
        u.last_name,
        p.phn_cell AS phone,
        c.card_number,
        b.name AS branch_name
    FROM auth_user u
    LEFT JOIN users_phone p ON u.id = p.user_id
    LEFT JOIN dma_cards c ON u.id = c.user_id
    LEFT JOIN office_branches b ON c.organization_id = b.id
    WHERE u.first_name LIKE ? 
       OR u.last_name LIKE ? 
       OR (u.first_name || ' ' || u.last_name) LIKE ?
       OR u.card_name LIKE ?
       OR p.phn_cell LIKE ?
       OR p.phn_business LIKE ?
    LIMIT 1
    """
    cursor.execute(sql, (f"%{term}%", f"%{term}%", f"%{term}%", f"%{term}%", phone_query, phone_query))
    row = cursor.fetchone()
    conn.close()

    if row:
        fname = f"{row[1] or ''} {row[2] or ''}".strip() or f"User #{row[0]}"
        return {
            "user_id": row[0],
            "full_name": fname,
            "phone": row[3] or "N/A",
            "card_number": row[4] or "N/A",
            "branch_name": row[5] or "Main Office"
        }
    return None

import re

def fetch_unpunched_workers(date_str, office_time_str="10:00 AM"):
    """
    Tool function: Fetches all active workers who have not punched in by office_time_str on date_str.
    """
    return query_unpunched_employees(date_str=date_str, office_time_str=office_time_str)

def fetch_late_workers(date_str, office_time_str="10:00 AM", grace_minutes=15):
    """
    Tool function: Fetches all active workers who punched in late (after office_time + grace_minutes) on date_str.
    """
    from db import query_late_employees
    return query_late_employees(date_str=date_str, office_time_str=office_time_str, grace_minutes=grace_minutes)


def get_employee_attendance_history(user_id, limit=5):
    """
    Tool function: Fetches recent attendance log history for a specific employee.
    """
    conn = get_connection()
    cursor = conn.cursor()
    sql = """
    SELECT 
        l.id,
        l.checkin_time,
        l.checkout_time,
        b.name AS branch_name
    FROM office_attendance_logs l
    JOIN dma_cards c ON l.card_id = c.id
    LEFT JOIN office_branches b ON l.branch_id = b.id
    WHERE c.user_id = ?
    ORDER BY l.checkin_time DESC
    LIMIT ?
    """
    cursor.execute(sql, (user_id, limit))
    rows = cursor.fetchall()
    conn.close()

    history = []
    for r in rows:
        history.append({
            "log_id": r[0],
            "checkin_time": r[1],
            "checkout_time": r[2],
            "branch": r[3] or "Main Branch"
        })
    return history

def get_latest_attendance_date():
    """
    Tool function: Returns the most recent date from attendance logs.
    """
    dates = get_all_attendance_dates()
    if dates:
        return dates[0]
    return "2026-10-04"

if __name__ == "__main__":
    print("[TOOLS] Testing 15-minute safe time threshold...")
    print(is_past_reminder_threshold("10:00 AM", "10:10 AM", grace_minutes=15))
    print(is_past_reminder_threshold("10:00 AM", "10:15 AM", grace_minutes=15))
    print(is_past_reminder_threshold("10:00 AM", "10:16 AM", grace_minutes=15))

    print("\n[TOOLS] Testing DB verification...")
    emp = verify_employee_in_db("Hasan Rahman")
    print("Found employee:", emp)
    emp_fake = verify_employee_in_db("Fake Employee 123")
    print("Fake employee search:", emp_fake)
