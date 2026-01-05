#!/usr/bin/env python3
"""
Intelligent Router Hook (PreToolUse for MCP calls)

Routes MCP calls through the orchestrator for intelligent handling.
Per the END GOAL: "The system figures out which MCP, which workflow, when, how"

This hook:
1. Intercepts MCP tool calls
2. Validates against user preferences and policies
3. Routes to the correct handler
4. Optionally modifies inputs based on context
"""

import json
import sys
import os
import re
from datetime import datetime
from pathlib import Path


def get_project_dir():
    return os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd())


def load_user_preferences():
    """Load user preferences from memory store."""
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


def load_org_policies():
    """Load organizational policies."""
    policies_file = Path(get_project_dir()) / "state" / "policies.json"
    if policies_file.exists():
        try:
            return json.loads(policies_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def check_risk_level(mcp_server: str, mcp_tool: str, tool_input: dict) -> str:
    """Determine risk level for this MCP operation."""
    # High risk operations
    high_risk = {
        "filesystem": ["delete_file", "write_file"],
        "github": ["delete_repo", "force_push"],
        "database": ["drop_table", "delete_all"],
    }

    # Medium risk operations
    medium_risk = {
        "github": ["create_pr", "merge_pr", "create_issue"],
        "filesystem": ["move_file", "rename_file"],
    }

    if mcp_server in high_risk and mcp_tool in high_risk[mcp_server]:
        return "high"
    if mcp_server in medium_risk and mcp_tool in medium_risk[mcp_server]:
        return "medium"
    return "low"


def main():
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    # Parse MCP tool name: mcp__<server>__<tool>
    mcp_match = re.match(r"mcp__(\w+)__(.+)", tool_name)
    if not mcp_match:
        sys.exit(0)  # Not an MCP tool

    mcp_server, mcp_tool = mcp_match.groups()

    # Load context
    user_prefs = load_user_preferences()
    org_policies = load_org_policies()

    # Check risk level
    risk = check_risk_level(mcp_server, mcp_tool, tool_input)

    # Get user's risk tolerance
    risk_tolerance = user_prefs.get("risk_tolerance", "medium")
    auto_approve_low_risk = user_prefs.get("auto_approve_low_risk", True)

    # Decision logic
    decision = "allow"
    reason = "Approved by routing policy"

    if risk == "high":
        if risk_tolerance == "low":
            decision = "deny"
            reason = f"High-risk operation {mcp_server}:{mcp_tool} blocked by low risk tolerance policy"
        else:
            decision = "ask"
            reason = f"High-risk operation {mcp_server}:{mcp_tool} requires confirmation"

    elif risk == "medium":
        if risk_tolerance == "low":
            decision = "ask"
            reason = f"Medium-risk operation {mcp_server}:{mcp_tool} requires confirmation under low risk tolerance"

    elif risk == "low" and auto_approve_low_risk:
        decision = "allow"
        reason = "Low-risk operation auto-approved"

    # Log routing decision
    log_file = Path(get_project_dir()) / "state" / "routing.jsonl"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "mcp_server": mcp_server,
        "mcp_tool": mcp_tool,
        "risk_level": risk,
        "decision": decision,
        "reason": reason,
    }

    with open(log_file, "a", encoding="utf-8") as f:
        json.dump(log_entry, f)
        f.write("\n")

    # Output decision
    if decision == "deny":
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason
            }
        }
        print(json.dumps(output))
        sys.exit(0)

    elif decision == "ask":
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": reason
            }
        }
        print(json.dumps(output))
        sys.exit(0)

    # Allow - exit 0 with no output means approved
    sys.exit(0)


if __name__ == "__main__":
    main()
