import os
import sqlite3
import re
from datetime import datetime

SQL_FILE = os.path.join(os.path.dirname(__file__), "dcard.sql")
DB_FILE = os.path.join(os.path.dirname(__file__), "dcard.db")

def init_db(force=False):
    if os.path.exists(DB_FILE) and not force:
        return

    print(f"[DB] Initializing SQLite database '{DB_FILE}' from '{SQL_FILE}'...")
    if not os.path.exists(SQL_FILE):
        raise FileNotFoundError(f"SQL file not found at {SQL_FILE}")

    with open(SQL_FILE, "r", encoding="utf-8", errors="ignore") as f:
        sql_text = f.read()

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Find CREATE TABLE blocks
    create_table_blocks = re.findall(
        r'CREATE TABLE [`\"]?(\w+)[`\"]?\s*\((.*?)\)\s*ENGINE=.*?;', 
        sql_text, 
        re.DOTALL | re.IGNORECASE
    )

    table_columns = {}
    for tbl_name, body in create_table_blocks:
        col_names = []
        for line in body.splitlines():
            line_str = line.strip()
            col_match = re.match(r'^`(\w+)`', line_str)
            if col_match:
                col_names.append(col_match.group(1))
        table_columns[tbl_name] = col_names

        # Create table in SQLite
        col_defs = []
        for col in col_names:
            if col == 'id':
                col_defs.append('"id" INTEGER PRIMARY KEY')
            else:
                col_defs.append(f'"{col}" TEXT')
        
        create_sql = f'CREATE TABLE IF NOT EXISTS "{tbl_name}" (\n  ' + ",\n  ".join(col_defs) + "\n);"
        cursor.execute(f'DROP TABLE IF EXISTS "{tbl_name}"')
        cursor.execute(create_sql)

    # Function to parse values tuple string like: (1, 'Admin', NULL), (2, 'DMA', '2023-01-01')
    def parse_values(vals_str, expected_cols):
        vals_str = vals_str.strip().rstrip(';')
        rows = []
        # Pattern to extract rows enclosed in parentheses
        # Handled by iterating tokens carefully
        tuple_matches = re.findall(r'\((.*?)\)(?:,\s*|\s*$)', vals_str, re.DOTALL)
        for t_content in tuple_matches:
            tokens = []
            cur = []
            in_q = False
            q_char = None
            for ch in t_content:
                if ch in ("'", '"'):
                    if not in_q:
                        in_q = True
                        q_char = ch
                    elif q_char == ch:
                        in_q = False
                        q_char = None
                    else:
                        cur.append(ch)
                elif ch == ',' and not in_q:
                    tokens.append("".join(cur).strip())
                    cur = []
                else:
                    cur.append(ch)
            if cur:
                tokens.append("".join(cur).strip())

            parsed_row = []
            for t in tokens:
                if t.upper() == 'NULL':
                    parsed_row.append(None)
                elif (t.startswith("'") and t.endswith("'")) or (t.startswith('"') and t.endswith('"')):
                    parsed_row.append(t[1:-1])
                else:
                    try:
                        parsed_row.append(int(t))
                    except ValueError:
                        try:
                            parsed_row.append(float(t))
                        except ValueError:
                            parsed_row.append(t)
            if len(parsed_row) == expected_cols:
                rows.append(parsed_row)
        return rows

    # Process line-by-line for inserts
    for line in sql_text.splitlines():
        line_str = line.strip()
        if line_str.lower().startswith("insert  into") or line_str.lower().startswith("insert into"):
            m = re.match(r'insert\s+into\s+[`\"]?(\w+)[`\"]?\s*\((.*?)\)\s*values\s*(.*)', line_str, re.IGNORECASE)
            if m:
                tbl_name = m.group(1)
                cols_str = m.group(2)
                vals_str = m.group(3)

                cols = [c.strip(" `\"") for c in cols_str.split(",")]
                col_list = ", ".join([f'"{c}"' for c in cols])
                placeholders = ", ".join(["?"] * len(cols))

                rows = parse_values(vals_str, len(cols))
                if rows:
                    cursor.executemany(f'INSERT INTO "{tbl_name}" ({col_list}) VALUES ({placeholders})', rows)

    conn.commit()
    conn.close()
    print("[DB] Database initial setup successfully finished.")

def get_connection():
    if not os.path.exists(DB_FILE):
        init_db()
    return sqlite3.connect(DB_FILE)

def query_unpunched_employees(date_str, office_time_str="10:00:00"):
    """
    Returns list of active employees who have NOT punched in on date_str.
    """
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
    SELECT 
        u.id AS user_id,
        u.first_name,
        u.last_name,
        p.phn_cell AS phone,
        c.card_number,
        c.id AS card_id,
        b.name AS branch_name
    FROM auth_user u
    LEFT JOIN users_phone p ON u.id = p.user_id
    LEFT JOIN dma_cards c ON u.id = c.user_id
    LEFT JOIN office_branches b ON c.organization_id = b.id
    WHERE u.is_active = 1
    ORDER BY u.id ASC
    """
    cursor.execute(sql)
    employees = cursor.fetchall()

    unpunched = []
    seen_users = set()

    for emp in employees:
        user_id, first_name, last_name, phone, card_number, card_id, branch_name = emp
        if user_id in seen_users:
            continue
        seen_users.add(user_id)

        full_name = f"{first_name or ''} {last_name or ''}".strip()
        if not full_name:
            full_name = f"Employee #{user_id}"

        # Check attendance log for card_id or user checkin on date_str
        log_sql = """
        SELECT checkin_time 
        FROM office_attendance_logs 
        WHERE card_id = ? 
          AND DATE(checkin_time) = DATE(?)
        LIMIT 1
        """
        punched = False
        punch_time = None
        if card_id:
            cursor.execute(log_sql, (card_id, date_str))
            log = cursor.fetchone()
            if log:
                punched = True
                punch_time = log[0]

        if not punched:
            unpunched.append({
                "user_id": user_id,
                "full_name": full_name,
                "phone": phone or "N/A",
                "card_number": card_number or "N/A",
                "branch_name": branch_name or "Main Branch",
                "punched": False,
                "checkin_time": None
            })

    conn.close()
    return unpunched

def query_late_employees(date_str, office_time_str="10:00 AM", grace_minutes=15):
    """
    Returns list of active employees who punched in on date_str AFTER (office_time + grace_minutes).
    """
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
    SELECT 
        u.id AS user_id,
        u.first_name,
        u.last_name,
        p.phn_cell AS phone,
        c.card_number,
        c.id AS card_id,
        b.name AS branch_name
    FROM auth_user u
    LEFT JOIN users_phone p ON u.id = p.user_id
    LEFT JOIN dma_cards c ON u.id = c.user_id
    LEFT JOIN office_branches b ON c.organization_id = b.id
    WHERE u.is_active = 1
    ORDER BY u.id ASC
    """
    cursor.execute(sql)
    employees = cursor.fetchall()

    late_comers = []
    seen_users = set()

    # Parse office time
    from tools import parse_time
    t_off = parse_time(office_time_str)
    if not t_off:
        t_off = parse_time("10:00 AM")
    
    m_off = t_off.hour * 60 + t_off.minute
    m_thresh = m_off + grace_minutes

    for emp in employees:
        user_id, first_name, last_name, phone, card_number, card_id, branch_name = emp
        if user_id in seen_users:
            continue
        seen_users.add(user_id)

        full_name = f"{first_name or ''} {last_name or ''}".strip() or f"Employee #{user_id}"

        # Check attendance log
        log_sql = """
        SELECT checkin_time 
        FROM office_attendance_logs 
        WHERE card_id = ? 
          AND DATE(checkin_time) = DATE(?)
        ORDER BY checkin_time ASC
        LIMIT 1
        """
        if card_id:
            cursor.execute(log_sql, (card_id, date_str))
            log = cursor.fetchone()
            if log and log[0]:
                checkin_time_str = log[0] # e.g. "2026-10-04 10:20:00"
                # Extract time part
                time_part = checkin_time_str.split(' ')[1] if ' ' in checkin_time_str else checkin_time_str
                t_chk = parse_time(time_part)
                if t_chk:
                    m_chk = t_chk.hour * 60 + t_chk.minute
                    if m_chk > m_thresh:
                        late_comers.append({
                            "user_id": user_id,
                            "full_name": full_name,
                            "phone": phone or "N/A",
                            "card_number": card_number or "N/A",
                            "branch_name": branch_name or "Main Branch",
                            "checkin_time": checkin_time_str
                        })

    conn.close()
    return late_comers


def get_all_attendance_dates():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT DATE(checkin_time) FROM office_attendance_logs WHERE checkin_time IS NOT NULL ORDER BY checkin_time DESC")
    dates = [r[0] for r in cursor.fetchall() if r[0]]
    conn.close()
    return dates

if __name__ == "__main__":
    init_db(force=True)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM auth_user")
    print("Total users:", cursor.fetchone()[0])
    cursor.execute("SELECT COUNT(*) FROM office_attendance_logs")
    print("Total attendance logs:", cursor.fetchone()[0])
    dates = get_all_attendance_dates()
    print(f"Total attendance dates found: {len(dates)}")
    if dates:
        print("Sample date for testing:", dates[0])
        unpunched = query_unpunched_employees(dates[0])
        print(f"Unpunched employees on {dates[0]}: {len(unpunched)}")
        if unpunched:
            print("First 3 unpunched employees:")
            for e in unpunched[:3]:
                print(f" - {e['full_name']} | Phone: {e['phone']} | Card: {e['card_number']}")
    conn.close()
