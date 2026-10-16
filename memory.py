"""
memory.py - Memory & CSV Log Tracking Module for Attendance Agent
Tracks generated reminders in JSON memory and logs every sent message to CSV file `sent_reminders_log.csv`.
Can be run individually: python3 memory.py
"""

import os
import json
import csv
from datetime import datetime

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "agent_memory.json")
CSV_FILE = os.path.join(os.path.dirname(__file__), "sent_reminders_log.csv")

class AgentMemory:
    def __init__(self, memory_filepath=MEMORY_FILE, csv_filepath=CSV_FILE):
        self.filepath = memory_filepath
        self.csv_path = csv_filepath
        self.memory = self._load_memory()
        self._init_csv()

    def _load_memory(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"reminders_sent": [], "session_logs": []}

    def _init_csv(self):
        """Ensures CSV file exists with proper headers."""
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Timestamp",
                    "User_ID",
                    "Full_Name",
                    "Phone",
                    "Card_Number",
                    "Branch_Name",
                    "Target_Date",
                    "Office_Time",
                    "Check_Time",
                    "Message"
                ])

    def save_memory(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.memory, f, indent=2)

    def is_reminder_sent(self, user_id, date_str):
        key = f"{user_id}_{date_str}"
        return key in self.memory["reminders_sent"]

    def record_reminder(self, user_id, full_name, phone, message, date_str, office_time, check_time, card_number="N/A", branch_name="Main Office"):
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        key = f"{user_id}_{date_str}"

        # 1. Record in JSON memory
        record = {
            "key": key,
            "user_id": user_id,
            "full_name": full_name,
            "phone": phone,
            "card_number": card_number,
            "branch_name": branch_name,
            "message": message,
            "date": date_str,
            "office_time": office_time,
            "check_time": check_time,
            "timestamp": now_str
        }

        if key not in self.memory["reminders_sent"]:
            self.memory["reminders_sent"].append(key)
        self.memory["session_logs"].append(record)
        self.save_memory()

        # 2. Append to CSV file
        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                now_str,
                user_id,
                full_name,
                phone,
                card_number,
                branch_name,
                date_str,
                office_time,
                check_time,
                message.replace("\n", " ")
            ])

        print(f"[MEMORY] Appended reminder log for '{full_name}' ({phone}) to '{os.path.basename(self.csv_path)}'")

    def get_session_history(self):
        return self.memory.get("session_logs", [])

if __name__ == "__main__":
    mem = AgentMemory()
    print(f"[MEMORY] Initialized.")
    print(f"[MEMORY] Memory File: {MEMORY_FILE}")
    print(f"[MEMORY] CSV Log File: {CSV_FILE}")
    print(f"[MEMORY] Total logged records: {len(mem.get_session_history())}")
