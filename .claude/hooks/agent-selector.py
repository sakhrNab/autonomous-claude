#!/usr/bin/env python3
"""
Agent Selector Hook (PreToolUse for Task/subagent)

Selects the right agent type for subagent tasks.
Per the END GOAL: "The system figures out which MCP, which workflow"

This hook:
1. Intercepts Task tool calls
2. Analyzes the task description
3. Suggests the optimal agent type
4. Optionally modifies the subagent_type parameter
"""

import json
import sys
import os
import re
from datetime import datetime
from pathlib import Path


def get_project_dir():
    return os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd())


def analyze_task_for_agent(description: str, prompt: str) -> str:
    """Determine the best agent type for a task."""
    text = (description + " " + prompt).lower()

    # Agent selection rules
    agent_rules = {
        "Explore": [
            "find", "search", "locate", "where is", "look for",
            "explore", "discover", "browse", "navigate", "scan"
        ],
        "Plan": [
            "plan", "design", "architect", "strategy", "approach",
            "how to implement", "implementation plan", "steps to"
        ],
        "general-purpose": [
            "complex", "multi-step", "research", "investigate",
            "analyze", "understand", "figure out"
        ],
    }

    # Score each agent type
    scores = {}
    for agent_type, keywords in agent_rules.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[agent_type] = score

    if not scores:
        return "general-purpose"  # Default

    return max(scores, key=scores.get)


def main():
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    if tool_name != "Task":
        sys.exit(0)

    tool_input = hook_input.get("tool_input", {})
    description = tool_input.get("description", "")
    prompt = tool_input.get("prompt", "")
    current_agent = tool_input.get("subagent_type", "")

    # Analyze and suggest agent
    suggested_agent = analyze_task_for_agent(description, prompt)

    # Log selection
    log_file = Path(get_project_dir()) / "state" / "agent-selections.jsonl"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "description": description[:100],
        "current_agent": current_agent,
        "suggested_agent": suggested_agent,
    }

    with open(log_file, "a", encoding="utf-8") as f:
        json.dump(log_entry, f)
        f.write("\n")

    # If no agent specified or we have a better suggestion, modify
    if not current_agent or current_agent != suggested_agent:
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": f"Agent selected: {suggested_agent}",
                "updatedInput": {
                    **tool_input,
                    "subagent_type": suggested_agent if not current_agent else current_agent
                }
            }
        }
        print(json.dumps(output))

    sys.exit(0)


if __name__ == "__main__":
    main()
