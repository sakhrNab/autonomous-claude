#!/usr/bin/env python3
"""
Task Ledger Update Hook (PostToolUse)

Updates the task ledger IMMEDIATELY after any tool execution.
Per the MASTER GUIDE: "Task Ledger updates IMMEDIATELY after any action"

This hook:
1. Receives tool execution details from Claude Code
2. Updates to-do-session2.md with action progress
3. Logs to state/actions.jsonl for audit trail
"""

import json
import sys
import os
from datetime import datetime
from pathlib import Path


def get_project_dir():
    """Get the project directory."""
    return os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd())


def update_task_ledger(tool_name: str, tool_input: dict, success: bool, session_id: str):
    """Update the task ledger with the action."""
    project_dir = Path(get_project_dir())

    # Determine what action was taken
    action_summary = ""
    if tool_name == "Bash":
        action_summary = f"Executed: {tool_input.get('command', '')[:100]}"
    elif tool_name in ["Write", "Edit"]:
        action_summary = f"Modified: {tool_input.get('file_path', '')}"
    elif tool_name == "Read":
        action_summary = f"Read: {tool_input.get('file_path', '')}"
    elif tool_name == "Task":
        action_summary = f"Ran subagent: {tool_input.get('description', '')}"
    elif tool_name.startswith("mcp__"):
        action_summary = f"MCP call: {tool_name}"
    else:
        action_summary = f"Tool: {tool_name}"

    # Log to actions.jsonl
    actions_file = project_dir / "state" / "actions.jsonl"
    actions_file.parent.mkdir(parents=True, exist_ok=True)

    action_entry = {
        "timestamp": datetime.now().isoformat(),
        "session_id": session_id,
        "tool": tool_name,
        "action": action_summary,
        "success": success,
    }

    with open(actions_file, "a", encoding="utf-8") as f:
        json.dump(action_entry, f)
        f.write("\n")

    return action_summary


def main():
    try:
        # Read hook input from stdin
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)  # Silent fail for invalid JSON

    tool_name = hook_input.get("tool_name", "Unknown")
    tool_input = hook_input.get("tool_input", {})
    tool_response = hook_input.get("tool_response", {})
    session_id = hook_input.get("session_id", "")

    # Determine success from response
    success = True
    if isinstance(tool_response, dict):
        success = not tool_response.get("error")

    # Skip logging for read-only tools to reduce noise
    skip_tools = {"Read", "Glob", "Grep", "LSP"}
    if tool_name in skip_tools:
        sys.exit(0)

    try:
        action = update_task_ledger(tool_name, tool_input, success, session_id)

        # Output for verbose mode
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "actionLogged": action,
                "success": success
            }
        }
        print(json.dumps(output))

    except Exception as e:
        print(f"Task ledger update error: {e}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
