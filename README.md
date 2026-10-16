# Agent For DMA

An AI-powered attendance reminder agent for **DMA** employees. The agent analyzes punch logs, determines late arrivals or unpunched employees past the scheduled threshold, and generates professional, polite reminder notifications via LLM (Groq API).

## Features

- **Punch Verification**: Detects missing or late attendance punches based on scheduled office hours.
- **AI-Powered Reminders**: Generates personalized reminder messages using Groq LLM with dynamic moderation prompts (`system_prompt.txt`).
- **Holiday & Grace Time Handling**: Respects weekends (Fridays), national holidays, and customizable grace thresholds.
- **Deduplication & Memory**: Tracks sent reminders in `agent_memory.json` and logs activity in `sent_reminders_log.csv`.
- **Interactive & Manual Input**: Supports manual inputs and batch runs via CLI.

## Project Structure

- `agent.py` - Attendance reminder generator interfacing with Groq API.
- `main.py` - Core orchestrator for DB queries, memory, holiday rules, and LLM output.
- `db.py` - SQLite database initialization and management from SQL dumps.
- `tools.py` - Attendance queries, employee roster lookups, and schedule checks.
- `memory.py` - In-memory and disk persistence for reminder deduplication.
- `manual_input.py` - CLI tool for manual punch check and simulation.
- `run_all.py` - Quick script to run the agent across all test cases.
- `system_prompt.txt` - Customizable prompt instructions for LLM tone and style.

## Quick Start

1. **Clone the repository**:
   ```bash
   git clone https://github.com/rahat300809/Agent_For_DMA.git
   cd Agent_For_DMA
   ```

2. **Configure Environment Variables**:
   Copy the example environment file and add your Groq API key:
   ```bash
   cp .env.example .env
   # Edit .env and set your GROQ_API_KEY
   ```

3. **Run the Agent**:
   ```bash
   # Run automated reminder check
   python3 main.py

   # Interactive CLI mode
   python3 main.py --interactive

   # Manual input simulation
   python3 manual_input.py
   ```
