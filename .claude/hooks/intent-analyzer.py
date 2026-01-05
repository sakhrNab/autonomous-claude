#!/usr/bin/env python3
"""
Intent Analyzer Hook (UserPromptSubmit)

Analyzes user intent and adds routing context.
Per the END GOAL: "You give intent, not instructions"

This hook:
1. Analyzes the user's message
2. Detects if it's a "handle this for me" request
3. Adds orchestrator context for autonomous handling
4. Learns user patterns over time
"""

import json
import sys
import os
import re
from datetime import datetime
from pathlib import Path


def get_project_dir():
    return os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd())


def detect_delegation_intent(prompt: str) -> bool:
    """Detect if user wants to delegate (handle this for me)."""
    delegation_patterns = [
        r"handle this",
        r"take care of",
        r"deal with",
        r"figure out",
        r"just do it",
        r"make it happen",
        r"sort this out",
        r"fix this",
        r"resolve this",
        r"get this done",
        r"you decide",
        r"your call",
        r"autonomous",
        r"on your own",
        r"without asking",
        r"don't ask",
        r"no confirmation needed",
    ]

    prompt_lower = prompt.lower()
    for pattern in delegation_patterns:
        if re.search(pattern, prompt_lower):
            return True
    return False


def detect_task_type(prompt: str) -> dict:
    """Detect the type of task from the prompt."""
    prompt_lower = prompt.lower()

    task_types = {
        "deployment": ["deploy", "release", "publish", "ship", "push to prod"],
        "monitoring": ["monitor", "watch", "alert", "check status", "health"],
        "debugging": ["debug", "fix", "error", "bug", "issue", "problem"],
        "automation": ["automate", "schedule", "recurring", "cron", "periodic"],
        "integration": ["integrate", "connect", "api", "mcp", "webhook"],
        "data": ["backup", "migrate", "sync", "transfer", "export", "import"],
    }

    detected = []
    for task_type, keywords in task_types.items():
        for keyword in keywords:
            if keyword in prompt_lower:
                detected.append(task_type)
                break

    return {"detected_types": list(set(detected))}


def load_user_history():
    """Load user's past requests for pattern learning."""
    history_file = Path(get_project_dir()) / "state" / "user_history.jsonl"
    if not history_file.exists():
        return []

    try:
        history = []
        with open(history_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    history.append(json.loads(line))
        return history[-20:]  # Last 20 requests
    except Exception:
        return []


def log_request(prompt: str, is_delegation: bool, task_types: list):
    """Log user request for learning."""
    log_file = Path(get_project_dir()) / "state" / "user_history.jsonl"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now().isoformat(),
        "prompt_preview": prompt[:200],
        "is_delegation": is_delegation,
        "task_types": task_types,
    }

    with open(log_file, "a", encoding="utf-8") as f:
        json.dump(entry, f)
        f.write("\n")


def main():
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    user_prompt = hook_input.get("user_prompt", "")
    if not user_prompt:
        sys.exit(0)

    # Analyze intent
    is_delegation = detect_delegation_intent(user_prompt)
    task_info = detect_task_type(user_prompt)

    # Log for learning
    log_request(user_prompt, is_delegation, task_info.get("detected_types", []))

    # Build additional context
    context_parts = []

    if is_delegation:
        context_parts.append("\n[AUTONOMOUS MODE DETECTED]")
        context_parts.append("User has delegated this task. You should:")
        context_parts.append("1. Figure out the best approach without asking")
        context_parts.append("2. Use appropriate MCPs and workflows automatically")
        context_parts.append("3. Only escalate for truly critical decisions")
        context_parts.append("4. Update the task ledger as you work")
        context_parts.append("5. Provide a summary when complete")

    if task_info.get("detected_types"):
        context_parts.append(f"\n[TASK TYPE: {', '.join(task_info['detected_types'])}]")

    # Add context to Claude's understanding
    if context_parts:
        output = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": "\n".join(context_parts)
            }
        }
        print(json.dumps(output))

    sys.exit(0)


if __name__ == "__main__":
    main()
