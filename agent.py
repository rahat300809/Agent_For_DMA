"""
agent.py - Attendance Reminder Agent using Groq API
Reads and saves system_prompt.txt dynamically for AI moderation.
Can be run individually: python3 agent.py
"""

import os
import json
import urllib.request
import urllib.error
def _load_env():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip().strip("'\""))
        except Exception:
            pass

_load_env()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
PROMPT_FILE = os.path.join(os.path.dirname(__file__), "system_prompt.txt")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# List of working Groq models for this API key
MODELS = ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b"]

def load_system_prompt():
    """Loads system prompt dynamically from writing file `system_prompt.txt`."""
    if os.path.exists(PROMPT_FILE):
        try:
            with open(PROMPT_FILE, "r", encoding="utf-8") as f:
                prompt = f.read().strip()
                if prompt:
                    return prompt
        except Exception as e:
            print(f"[AGENT WARNING] Error reading system_prompt.txt: {e}")

    default_prompt = (
        "You are an Attendance Officer AI Agent for DMA. Your job is to generate polite, "
        "professional, and clear SMS/WhatsApp reminder messages to employees who have not "
        "punched their attendance card by the required office start time."
    )
    save_system_prompt(default_prompt)
    return default_prompt

def save_system_prompt(prompt_text):
    """Saves new system prompt to system_prompt.txt."""
    with open(PROMPT_FILE, "w", encoding="utf-8") as f:
        f.write(prompt_text.strip())
    print(f"[AGENT] Saved updated system prompt to '{PROMPT_FILE}'")

def call_groq_api(system_prompt, user_prompt):
    """Calls Groq Chat Completions API with dynamic system prompt and fallback models."""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Python)"
    }

    for model in MODELS:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 200
        }
        req = urllib.request.Request(
            GROQ_API_URL, 
            data=json.dumps(payload).encode("utf-8"), 
            headers=headers
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                content = res_data["choices"][0]["message"]["content"].strip()
                if content:
                    return content
        except Exception:
            continue

    return None

def generate_reminder(employee, office_time="10:00 AM", check_time="10:20 AM", date_str=None):
    """
    Generates a personalized punch reminder message for an employee using system_prompt.txt.
    """
    full_name = employee.get("full_name", "Employee")
    phone = employee.get("phone", "N/A")
    branch = employee.get("branch_name", "Office")
    actual_checkin = employee.get("checkin_time")

    system_prompt = load_system_prompt()
    
    if actual_checkin:
        status_line = f"- Status: Card punched LATE at {actual_checkin}"
        fallback = (
            f"Dear {full_name}, your office time started at {office_time}, but you punched in late at {actual_checkin}. "
            f"Please ensure you arrive on time."
        )
    else:
        status_line = f"- Status: Card NOT punched yet"
        fallback = (
            f"Dear {full_name}, your office time started at {office_time}, but as of {check_time}, "
            f"your attendance card punch has not been recorded. Please punch your card immediately."
        )

    user_prompt = (
        f"Generate an attendance card punch reminder message for:\n"
        f"- Full Name: {full_name}\n"
        f"- Phone: {phone}\n"
        f"- Office Branch: {branch}\n"
        f"- Date: {date_str or 'Today'}\n"
        f"- Scheduled Office Time: {office_time}\n"
        f"- Current Check Time: {check_time}\n"
        f"{status_line}\n\n"
        f"Strictly adhere to system prompt guidelines. Write a concise reminder message for {full_name}."
    )

    ai_message = call_groq_api(system_prompt, user_prompt)

    if not ai_message:
        # Fallback template if network/API is unavailable
        ai_message = fallback

    return ai_message

if __name__ == "__main__":
    print("[AGENT] Testing Groq Attendance Agent...")
    current_prompt = load_system_prompt()
    print("System Prompt Loaded:\n", current_prompt)
    sample_emp = {
        "user_id": 7,
        "full_name": "Hasan Rahman",
        "phone": "01919968025",
        "branch_name": "DMA (Gulshan)"
    }
    print("\n--- Generating Sample Reminder ---")
    msg = generate_reminder(sample_emp, office_time="10:00 AM", check_time="10:20 AM", date_str="2026-10-10")
    print(f"Employee: {sample_emp['full_name']}")
    print(f"Phone:    {sample_emp['phone']}")
    print(f"Message:  {msg}")
