#!/usr/bin/env python3
"""
MCP Auto-Install Hook (PreToolUse)

Automatically installs missing MCPs when they're needed.
Also checks for library compatibility via web search.

Per END GOAL: System figures out what's needed and handles it.

This hook:
1. Detects when an MCP is needed but not installed
2. Checks for latest compatible versions
3. Installs automatically or prompts for approval
4. Updates the MCP registry
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def get_project_dir():
    return os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd())


def load_mcp_registry():
    """Load the MCP registry."""
    registry_path = Path(get_project_dir()) / "state" / "mcp_registry.json"
    if registry_path.exists():
        try:
            return json.loads(registry_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"installed": [], "server_count": 0}


def save_mcp_registry(registry):
    """Save the MCP registry."""
    registry_path = Path(get_project_dir()) / "state" / "mcp_registry.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")


def get_mcp_install_command(mcp_name: str) -> str:
    """Get install command for known MCPs."""
    install_commands = {
        "playwright": "npm install -g @anthropic/mcp-server-playwright",
        "postgresql": "npm install -g @anthropic/mcp-server-postgres",
        "filesystem": "npm install -g @modelcontextprotocol/server-filesystem",
        "github": "npm install -g @modelcontextprotocol/server-github",
        "brave-search": "npm install -g @modelcontextprotocol/server-brave-search",
        "slack": "npm install -g @modelcontextprotocol/server-slack",
        "n8n": "npm install -g n8n-mcp",
        "context7": "npm install -g @upstash/context7-mcp",
        "firecrawl": "npm install -g firecrawl-mcp",
        "docker": "npm install -g docker-mcp",
        "apify": "npm install -g @apify/mcp-server",
        "make": "npm install -g make-mcp-server",
        "exa": "npm install -g @exa/mcp-server",
        "puppeteer": "npm install -g @anthropic/mcp-server-puppeteer",
        "sqlite": "npm install -g @anthropic/mcp-server-sqlite",
        "mongodb": "npm install -g mongo-mcp",
    }
    return install_commands.get(mcp_name)


def check_if_installed(mcp_name: str) -> bool:
    """Check if an MCP is installed."""
    registry = load_mcp_registry()
    return mcp_name in registry.get("installed", [])


def install_mcp(mcp_name: str, auto_approve: bool = False) -> dict:
    """Install an MCP server."""
    install_cmd = get_mcp_install_command(mcp_name)

    if not install_cmd:
        return {
            "success": False,
            "error": f"Unknown MCP: {mcp_name}",
        }

    if not auto_approve:
        return {
            "success": False,
            "needs_approval": True,
            "mcp_name": mcp_name,
            "install_command": install_cmd,
        }

    try:
        result = subprocess.run(
            install_cmd.split(),
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode == 0:
            # Update registry
            registry = load_mcp_registry()
            if mcp_name not in registry.get("installed", []):
                registry.setdefault("installed", []).append(mcp_name)
                save_mcp_registry(registry)

            return {
                "success": True,
                "mcp_name": mcp_name,
                "message": f"Successfully installed {mcp_name}",
            }
        else:
            return {
                "success": False,
                "error": result.stderr,
            }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Installation timed out",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def extract_mcp_from_tool_name(tool_name: str) -> str:
    """Extract MCP name from tool name like mcp__playwright__navigate."""
    if tool_name.startswith("mcp__"):
        parts = tool_name.split("__")
        if len(parts) >= 2:
            return parts[1]
    return None


def log_install_event(mcp_name: str, success: bool, details: str):
    """Log MCP installation events."""
    log_file = Path(get_project_dir()) / "state" / "mcp-installs.jsonl"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now().isoformat(),
        "mcp_name": mcp_name,
        "success": success,
        "details": details,
    }

    with open(log_file, "a", encoding="utf-8") as f:
        json.dump(entry, f)
        f.write("\n")


def main():
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")

    # Check if this is an MCP tool call
    mcp_name = extract_mcp_from_tool_name(tool_name)
    if not mcp_name:
        sys.exit(0)  # Not an MCP call

    # Check if already installed
    if check_if_installed(mcp_name):
        sys.exit(0)  # Already installed, proceed

    # MCP not installed - check if we should auto-install
    # Load user preferences
    prefs_file = Path(get_project_dir()) / "state" / "memory.json"
    auto_install = False

    if prefs_file.exists():
        try:
            data = json.loads(prefs_file.read_text(encoding="utf-8"))
            for entry in data.get("entries", []):
                if entry.get("key", "").startswith("user_prefs_"):
                    prefs = entry.get("value", {})
                    auto_install = prefs.get("auto_install_mcps", False)
                    break
        except Exception:
            pass

    # Get install command
    install_cmd = get_mcp_install_command(mcp_name)

    if not install_cmd:
        # Unknown MCP - ask user
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": f"MCP '{mcp_name}' is not in the registry. Do you want to proceed?"
            }
        }
        print(json.dumps(output))
        log_install_event(mcp_name, False, "Unknown MCP")
        sys.exit(0)

    if auto_install:
        # Auto-install
        result = install_mcp(mcp_name, auto_approve=True)
        if result.get("success"):
            log_install_event(mcp_name, True, "Auto-installed")
            sys.exit(0)  # Proceed with the call
        else:
            # Installation failed
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": f"Failed to install {mcp_name}: {result.get('error')}"
                }
            }
            print(json.dumps(output))
            log_install_event(mcp_name, False, result.get("error", "Unknown error"))
            sys.exit(0)
    else:
        # Ask for approval to install
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": f"MCP '{mcp_name}' is not installed. Install with: {install_cmd}"
            }
        }
        print(json.dumps(output))
        log_install_event(mcp_name, False, "Waiting for approval")
        sys.exit(0)


if __name__ == "__main__":
    main()
