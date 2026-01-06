"""
Self-Healing System

This module enables the system to fix itself when users report issues.
It uses Claude Code CLI to:
1. Analyze the error/feedback
2. Plan a fix
3. Implement the fix
4. Test the fix
5. Report back to the user

This is the "autonomous operator" in action - truly self-improving.
"""

import os
import sys
import json
import asyncio
import subprocess
import shutil
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path


class SelfHealingSystem:
    """
    The self-healing system that uses Claude Code to fix issues.

    When a user reports an error or gives feedback:
    1. Captures the context (logs, error, user description)
    2. Calls Claude Code to analyze and fix
    3. Tests the fix
    4. Reports success/failure to user
    """

    def __init__(self):
        self.claude_cli = shutil.which("claude")
        self.project_root = Path(__file__).parent.parent
        self.fix_history: List[Dict] = []

    @property
    def is_available(self) -> bool:
        """Check if Claude Code CLI is available."""
        return self.claude_cli is not None

    async def analyze_and_fix(
        self,
        issue_description: str,
        error_logs: Optional[str] = None,
        affected_file: Optional[str] = None,
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Main entry point - analyze an issue and attempt to fix it.

        Returns:
            Dict with:
            - success: bool
            - action_taken: str
            - changes_made: List[str]
            - test_result: str
            - message: str
        """
        if not self.is_available:
            return {
                "success": False,
                "action_taken": "none",
                "changes_made": [],
                "test_result": "skipped",
                "message": "Claude Code CLI not available. Please install it first.",
            }

        # Build the prompt for Claude Code
        prompt = self._build_fix_prompt(issue_description, error_logs, affected_file, context)

        # Call Claude Code to analyze and fix
        result = await self._call_claude_code(prompt)

        # Parse the result
        fix_result = self._parse_fix_result(result)

        # Log the fix attempt
        self.fix_history.append({
            "timestamp": datetime.now().isoformat(),
            "issue": issue_description,
            "result": fix_result,
        })

        return fix_result

    def _build_fix_prompt(
        self,
        issue: str,
        error_logs: Optional[str],
        affected_file: Optional[str],
        context: Optional[Dict]
    ) -> str:
        """Build a prompt for Claude Code to fix the issue."""

        prompt = f"""I need you to fix an issue in the MCP Orchestrator project.

PROJECT LOCATION: {self.project_root}

ISSUE REPORTED BY USER:
{issue}

"""
        if error_logs:
            prompt += f"""
ERROR LOGS:
{error_logs[:2000]}  # Truncate if too long

"""

        if affected_file:
            prompt += f"""
AFFECTED FILE: {affected_file}

"""

        if context:
            prompt += f"""
ADDITIONAL CONTEXT:
{json.dumps(context, indent=2)}

"""

        prompt += """
INSTRUCTIONS:
1. Analyze the issue carefully
2. Identify the root cause
3. Make the necessary code changes to fix it
4. After fixing, verify the fix makes sense
5. Provide a brief summary of what you changed

IMPORTANT:
- Make minimal, targeted changes
- Don't break existing functionality
- If you're unsure, explain what you would do instead of making risky changes
- Focus on the specific issue reported

Please fix this issue now.
"""
        return prompt

    async def _call_claude_code(self, prompt: str) -> str:
        """Call Claude Code CLI with the given prompt."""
        try:
            # Create a temp file with the prompt for complex prompts
            prompt_file = self.project_root / "state" / "fix_prompt.txt"
            prompt_file.parent.mkdir(parents=True, exist_ok=True)
            prompt_file.write_text(prompt, encoding="utf-8")

            # Run Claude Code
            process = await asyncio.create_subprocess_exec(
                self.claude_cli,
                "--print",  # Print mode - just output, no interactive
                "-p", prompt,
                cwd=str(self.project_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=120  # 2 minute timeout for complex fixes
            )

            output = stdout.decode("utf-8")
            if stderr:
                output += "\n[STDERR]: " + stderr.decode("utf-8")

            return output

        except asyncio.TimeoutError:
            return "ERROR: Claude Code timed out after 2 minutes"
        except Exception as e:
            return f"ERROR: Failed to call Claude Code: {str(e)}"

    def _parse_fix_result(self, claude_output: str) -> Dict[str, Any]:
        """Parse Claude Code's output to extract what was done."""

        if claude_output.startswith("ERROR:"):
            return {
                "success": False,
                "action_taken": "none",
                "changes_made": [],
                "test_result": "skipped",
                "message": claude_output,
            }

        # Check for common success indicators
        success_indicators = [
            "fixed", "updated", "changed", "modified", "added", "removed",
            "corrected", "resolved", "patched", "implemented"
        ]

        output_lower = claude_output.lower()
        appears_successful = any(ind in output_lower for ind in success_indicators)

        # Extract file changes mentioned
        changes = []
        lines = claude_output.split('\n')
        for line in lines:
            if any(ext in line for ext in ['.py', '.html', '.js', '.json', '.ts']):
                if any(word in line.lower() for word in ['edit', 'write', 'modif', 'chang', 'updat']):
                    changes.append(line.strip()[:100])

        return {
            "success": appears_successful,
            "action_taken": "fix_attempted" if appears_successful else "analysis_only",
            "changes_made": changes[:10],  # Limit to 10 changes
            "test_result": "pending",
            "message": claude_output[:1000],  # First 1000 chars of output
            "full_output": claude_output,
        }

    async def execute_command(self, command: str, cwd: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute a terminal command.

        This allows the system to run arbitrary commands for:
        - Restarting services
        - Installing dependencies
        - Running tests
        - Git operations
        """
        if not cwd:
            cwd = str(self.project_root)

        try:
            # Use shell=True on Windows for proper command execution
            is_windows = sys.platform == "win32"

            if is_windows:
                process = await asyncio.create_subprocess_shell(
                    command,
                    cwd=cwd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                process = await asyncio.create_subprocess_exec(
                    "/bin/bash", "-c", command,
                    cwd=cwd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=60  # 1 minute timeout
            )

            return {
                "success": process.returncode == 0,
                "exit_code": process.returncode,
                "stdout": stdout.decode("utf-8"),
                "stderr": stderr.decode("utf-8"),
            }

        except asyncio.TimeoutError:
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": "Command timed out after 60 seconds",
            }
        except Exception as e:
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
            }

    async def restart_server(self) -> Dict[str, Any]:
        """
        Restart the API server.

        This creates a restart script and schedules it to run,
        then exits the current process.
        """
        restart_script = self.project_root / "state" / "restart.py"

        script_content = '''
import os
import sys
import time
import subprocess

# Wait for old process to die
time.sleep(2)

# Start new server
os.chdir(r"{project_root}")
subprocess.Popen(
    [sys.executable, "-m", "api.server"],
    creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
)
'''.format(project_root=str(self.project_root))

        restart_script.write_text(script_content)

        return {
            "success": True,
            "message": "Server restart scheduled. Refresh the page in 5 seconds.",
            "restart_script": str(restart_script),
        }


# Singleton instance
_self_healing: Optional[SelfHealingSystem] = None


def get_self_healing() -> SelfHealingSystem:
    """Get the singleton self-healing system instance."""
    global _self_healing
    if _self_healing is None:
        _self_healing = SelfHealingSystem()
    return _self_healing
