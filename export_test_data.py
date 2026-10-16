import sqlite3
import os

DB_FILE = os.path.join(os.path.dirname(__file__), "dcard.db")
TXT_FILE = os.path.join(os.path.dirname(__file__), "db_sample_employees.txt")
MD_FILE = os.path.join(os.path.dirname(__file__), "db_sample_employees.md")

def export_db_reference_data():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            u.id, 
            u.first_name, 
            u.last_name, 
            p.phn_cell, 
            c.card_number, 
            b.name AS branch_name
        FROM auth_user u
        LEFT JOIN users_phone p ON u.id = p.user_id
        LEFT JOIN dma_cards c ON u.id = c.user_id
        LEFT JOIN office_branches b ON c.organization_id = b.id
        WHERE u.is_active = 1
        ORDER BY u.id ASC
    """)
    rows = cursor.fetchall()
    conn.close()

    lines = [
        "====================================================================================================",
        "                     DCARD DATABASE - REGISTERED EMPLOYEE REFERENCE TEST DATA",
        "====================================================================================================",
        " Use these exact Names or Phone Numbers to test DB cross-checking in manual_input.py!",
        "====================================================================================================\n",
        f"{'ID':<6} | {'FULL NAME':<30} | {'PHONE NUMBER':<18} | {'CARD NUMBER':<18} | {'BRANCH':<20}",
        "-" * 102
    ]

    md_lines = [
        "# dcard Database - Registered Employee Reference Data",
        "",
        "Use these registered Names or Phone Numbers to test DB cross-checking in `manual_input.py`:",
        "",
        "| ID | Full Name | Phone Number | Card Number | Branch Name |",
        "|---|---|---|---|---|"
    ]

    for r in rows:
        user_id = r[0]
        full_name = f"{r[1] or ''} {r[2] or ''}".strip() or f"User #{user_id}"
        phone = r[3] or "N/A"
        card = r[4] or "N/A"
        branch = r[5] or "Main Branch"
        lines.append(f"{user_id:<6} | {full_name:<30} | {phone:<18} | {card:<18} | {branch:<20}")
        md_lines.append(f"| {user_id} | {full_name} | {phone} | {card} | {branch} |")

    with open(TXT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    with open(MD_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    print(f"[EXPORT] Created '{TXT_FILE}' and '{MD_FILE}' with {len(rows)} registered employee records.")

if __name__ == "__main__":
    export_db_reference_data()
