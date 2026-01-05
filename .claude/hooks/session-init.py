#!/usr/bin/env python3
"""
Session Initialization Hook (SessionStart)

Sets up context when Claude Code starts.
Per the END GOAL: "Memory with judgment - it remembers what you care about"

This hook:
1. Loads user preferences
2. Loads operational memory (past failures/fixes)
3. Loads current task state
4. Provides context to Claude
"""

import json
import sys
import os
from datetime import datetime
from pathlib import Path


def get_project_dir():
    return os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd())


def load_user_preferences():
    """Load user preferences."""
    prefs_file = Path(get_project_dir()) / "state" / "memory.json"
    if prefs_file.exists():
        try:
            data = json.loads(prefs_file.read_text(encoding="utf-8"))
            for entry in data.get("entries", []):
                if entry.get("key", "").startswith("user_prefs_"):
                    return entry.get("value", {})
        except Exception:
            pass
    return {}


def load_operational_memory():
    """Load past failures and fixes for learning."""
    memory_file = Path(get_project_dir()) / "state" / "memory.json"
    failures = []
    fixes = []

    if memory_file.exists():
        try:
            data = json.loads(memory_file.read_text(encoding="utf-8"))
            for entry in data.get("entries", []):
                key = entry.get("key", "")
                if key.startswith("failure_"):
                    failures.append(entry.get("value", {}))
                elif key.startswith("fix_"):
                    fixes.append(entry.get("value", {}))
        except Exception:
            pass

    return {"failures": failures[-5:], "fixes": fixes[-5:]}  # Last 5 of each


def load_current_tasks():
    """Load current task state."""
    project_dir = Path(get_project_dir())

    # Try tasks.json first
    tasks_json = project_dir / "tasks.json"
    if tasks_json.exists():
        try:
            data = json.loads(tasks_json.read_text(encoding="utf-8"))
            tasks = data.get("tasks", [])
            pending = [t for t in tasks if t.get("state") not in ["completed"]]
            return {
                "total": len(tasks),
                "pending": len(pending),
                "pending_tasks": [t.get("description", t.get("id")) for t in pending[:5]]
            }
        except Exception:
            pass

    return {"total": 0, "pending": 0, "pending_tasks": []}


def build_context():
    """Build the session context."""
    prefs = load_user_preferences()
    memory = load_operational_memory()
    tasks = load_current_tasks()

    context_parts = []

    # User preferences
    if prefs:
        context_parts.append("## User Preferences")
        context_parts.append(f"- Communication style: {prefs.get('communication_style', 'professional')}")
        context_parts.append(f"- Risk tolerance: {prefs.get('risk_tolerance', 'medium')}")
        context_parts.append(f"- Auto-approve low risk: {prefs.get('auto_approve_low_risk', True)}")
        if prefs.get("favorite_tools"):
            context_parts.append(f"- Preferred tools: {', '.join(prefs.get('favorite_tools', []))}")
        context_parts.append("")

    # Current task state
    if tasks.get("pending", 0) > 0:
        context_parts.append("## Current Tasks")
        context_parts.append(f"- {tasks.get('pending')} pending task(s) of {tasks.get('total')} total")
        for task in tasks.get("pending_tasks", []):
            context_parts.append(f"  - {task}")
        context_parts.append("")

    # Operational memory - past learnings
    if memory.get("failures") or memory.get("fixes"):
        context_parts.append("## Recent Learnings")
        if memory.get("fixes"):
            successful_fixes = [f for f in memory.get("fixes", []) if f.get("success")]
            if successful_fixes:
                context_parts.append(f"- {len(successful_fixes)} successful fix(es) in recent history")
        context_parts.append("")

    # Orchestrator skill available
    context_parts.append("## Available Orchestrator")
    context_parts.append("The autonomous-operator skill is available.")
    context_parts.append("You can delegate complex tasks by saying: 'Handle this for me'")
    context_parts.append("The orchestrator will figure out which MCP, workflow, and when to run.")
    context_parts.append("")

    return "\n".join(context_parts)


def main():
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        hook_input = {}

    context = build_context()

    # Set environment variables for the session
    env_file = os.environ.get('CLAUDE_ENV_FILE')
    if env_file:
        try:
            with open(env_file, 'a') as f:
                f.write('export ORCHESTRATOR_ENABLED=true\n')
                f.write(f'export SESSION_START_TIME="{datetime.now().isoformat()}"\n')
        except Exception:
            pass

    # Log session start
    log_file = Path(get_project_dir()) / "state" / "sessions.jsonl"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "event": "session_start",
        "session_id": hook_input.get("session_id", ""),
    }

    with open(log_file, "a", encoding="utf-8") as f:
        json.dump(log_entry, f)
        f.write("\n")

    # Output context for Claude
    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context
        }
    }
    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
