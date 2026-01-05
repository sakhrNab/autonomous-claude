#!/usr/bin/env python3
"""
Completion Checker Hook (Stop)

THE MOST IMPORTANT HOOK - Decides if Claude should stop or continue.
Per the MASTER GUIDE: "IF THE TO-DO IS NOT DONE, THE SYSTEM IS NOT DONE."

This hook:
1. Reads the task ledger
2. Checks if all tasks are complete
3. Checks if any messages have incomplete linked tasks
4. ONLY allows stop when everything is done
"""

import json
import sys
import os
import re
from datetime import datetime
from pathlib import Path


def get_project_dir():
    return os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd())


def parse_todo_file(todo_path: Path) -> dict:
    """Parse to-do.md or to-do-session2.md file."""
    if not todo_path.exists():
        return {"total": 0, "completed": 0, "incomplete": [], "blocked": []}

    content = todo_path.read_text(encoding="utf-8")

    completed = []
    incomplete = []
    blocked = []

    # Pattern: [x] completed, [ ] pending, [~] in progress, [!] blocked
    for match in re.finditer(r'\[([ x~!])\]\s*(\d+\.?\s*)?(.*?)(?:\n|$)', content, re.MULTILINE):
        status, num, description = match.groups()
        task = description.strip()[:100]

        if status == 'x':
            completed.append(task)
        elif status == '!':
            blocked.append(task)
        else:
            incomplete.append(task)

    return {
        "total": len(completed) + len(incomplete) + len(blocked),
        "completed": len(completed),
        "incomplete": incomplete,
        "blocked": blocked,
    }


def check_task_ledger():
    """Check both to-do.md and to-do-session2.md."""
    project_dir = Path(get_project_dir())

    # Check session 2 first (current session)
    session2 = project_dir / "to-do-session2.md"
    if session2.exists():
        result = parse_todo_file(session2)
        if result["incomplete"] or result["blocked"]:
            return result

    # Then check main to-do
    main_todo = project_dir / "to-do.md"
    if main_todo.exists():
        result = parse_todo_file(main_todo)
        if result["incomplete"] or result["blocked"]:
            return result

    # Check tasks.json for machine-readable state
    tasks_json = project_dir / "tasks.json"
    if tasks_json.exists():
        try:
            data = json.loads(tasks_json.read_text(encoding="utf-8"))
            incomplete = []
            blocked = []
            for task in data.get("tasks", []):
                state = task.get("state", "pending")
                if state == "blocked":
                    blocked.append(task.get("description", task.get("id", "unknown")))
                elif state != "completed":
                    incomplete.append(task.get("description", task.get("id", "unknown")))

            if incomplete or blocked:
                return {
                    "total": len(data.get("tasks", [])),
                    "completed": len([t for t in data.get("tasks", []) if t.get("state") == "completed"]),
                    "incomplete": incomplete,
                    "blocked": blocked,
                }
        except Exception:
            pass

    return {"total": 0, "completed": 0, "incomplete": [], "blocked": []}


def check_pending_messages():
    """Check if there are messages with incomplete linked tasks."""
    project_dir = Path(get_project_dir())
    messages_file = project_dir / "state" / "messages.json"

    if not messages_file.exists():
        return []

    try:
        data = json.loads(messages_file.read_text(encoding="utf-8"))
        pending = []
        for msg in data.get("messages", []):
            status = msg.get("status", "pending")
            if status not in ["completed", "failed"]:
                linked_tasks = msg.get("linked_tasks", [])
                if linked_tasks:
                    pending.append({
                        "message_id": msg.get("message_id", "")[:8],
                        "linked_tasks": linked_tasks,
                    })
        return pending
    except Exception:
        return []


def main():
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        hook_input = {}

    # Check task ledger
    task_status = check_task_ledger()
    incomplete_tasks = task_status.get("incomplete", [])
    blocked_tasks = task_status.get("blocked", [])

    # Check pending messages
    pending_messages = check_pending_messages()

    # Log check
    log_file = Path(get_project_dir()) / "state" / "stop-checks.jsonl"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "incomplete_tasks": len(incomplete_tasks),
        "blocked_tasks": len(blocked_tasks),
        "pending_messages": len(pending_messages),
    }

    with open(log_file, "a", encoding="utf-8") as f:
        json.dump(log_entry, f)
        f.write("\n")

    # Decision: Block stop if there are incomplete tasks or pending messages
    if incomplete_tasks or blocked_tasks:
        reasons = []
        if incomplete_tasks:
            reasons.append(f"{len(incomplete_tasks)} incomplete task(s): {incomplete_tasks[:3]}")
        if blocked_tasks:
            reasons.append(f"{len(blocked_tasks)} blocked task(s): {blocked_tasks[:3]}")

        output = {
            "decision": "block",
            "reason": "Task ledger not complete. " + "; ".join(reasons)
        }
        print(json.dumps(output))
        sys.exit(0)

    if pending_messages:
        output = {
            "decision": "block",
            "reason": f"{len(pending_messages)} message(s) have incomplete linked tasks. Complete all message-linked tasks before stopping."
        }
        print(json.dumps(output))
        sys.exit(0)

    # All complete - allow stop
    output = {
        "decision": "approve",
        "reason": f"All {task_status.get('total', 0)} tasks complete. Stopping allowed."
    }
    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
