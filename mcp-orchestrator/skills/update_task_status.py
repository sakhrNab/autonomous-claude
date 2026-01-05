"""
Update Task Status Skill

Updates the status of a task in the ledger.
Per the Master Guide, state transitions are validated.
"""

from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime
import json

from .base_skill import BaseSkill, SkillResult


class UpdateTaskStatus(BaseSkill):
    """
    Skill to update task status in the ledger.

    Task states:
    - pending: [ ] Not started
    - in_progress: [~] Currently working
    - completed: [x] Done (requires evidence)
    - blocked: [!] Cannot proceed

    Note: This skill performs the update, but the Task Manager Agent
    validates the transition.
    """

    name = "update_task_status"
    description = "Update the status of a task in the ledger"
    required_permissions = ["task:write"]
    estimated_cost = 0.0

    VALID_STATES = ["pending", "in_progress", "completed", "blocked"]
    STATE_SYMBOLS = {
        "pending": "[ ]",
        "in_progress": "[~]",
        "completed": "[x]",
        "blocked": "[!]",
    }

    async def execute(
        self,
        args: Dict[str, Any],
        context: Optional[Any] = None
    ) -> SkillResult:
        """
        Update task status.

        Args:
            args:
                - task_id: Task identifier
                - new_state: New state (pending, in_progress, completed, blocked)
                - evidence: Required if new_state is completed
                - reason: Required if new_state is blocked
                - json_path: Path to tasks.json
        """
        await self.pre_execute(args)

        task_id = args.get("task_id")
        new_state = args.get("new_state")
        evidence = args.get("evidence")
        reason = args.get("reason")
        json_path = Path(args.get("json_path", "tasks.json"))

        # Validate state
        if new_state not in self.VALID_STATES:
            return SkillResult(
                success=False,
                error=f"Invalid state: {new_state}. Must be one of {self.VALID_STATES}",
            )

        # Check requirements
        if new_state == "completed" and not evidence:
            return SkillResult(
                success=False,
                error="Evidence is required to mark a task as completed",
            )

        if new_state == "blocked" and not reason:
            return SkillResult(
                success=False,
                error="Reason is required to mark a task as blocked",
            )

        try:
            # Load current ledger
            if not json_path.exists():
                return SkillResult(
                    success=False,
                    error=f"Task ledger not found: {json_path}",
                )

            ledger = json.loads(json_path.read_text(encoding="utf-8"))

            # Find and update task
            task_found = False
            for task in ledger["tasks"]:
                if task["id"] == task_id:
                    task_found = True
                    old_state = task["state"]
                    task["state"] = new_state
                    task["updated_at"] = datetime.now().isoformat()

                    if evidence:
                        task["evidence"] = evidence
                    if reason:
                        task["blocked_reason"] = reason

                    break

            if not task_found:
                return SkillResult(
                    success=False,
                    error=f"Task not found: {task_id}",
                )

            # Update timestamp
            ledger["updated_at"] = datetime.now().isoformat()

            # Save updated ledger
            json_path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")

            # Also update markdown file
            self._update_markdown(ledger, Path(str(json_path).replace(".json", ".md").replace("tasks", "to-do")))

            skill_result = SkillResult(
                success=True,
                data={
                    "task_id": task_id,
                    "old_state": old_state,
                    "new_state": new_state,
                    "has_evidence": evidence is not None,
                },
                cost=0.0,
            )

        except Exception as e:
            skill_result = SkillResult(
                success=False,
                error=str(e),
            )

        await self.post_execute(skill_result)
        return skill_result

    def _update_markdown(self, ledger: Dict[str, Any], md_path: Path):
        """Update the markdown ledger file."""
        lines = [
            "# Task Ledger",
            f"Session: {ledger.get('session_id', 'unknown')}",
            f"Updated: {ledger.get('updated_at', datetime.now().isoformat())}",
            "",
            "## Core Tasks",
        ]

        for task in ledger.get("tasks", []):
            symbol = self.STATE_SYMBOLS.get(task["state"], "[ ]")
            lines.append(f"{symbol} {task['id']}: {task['description']}")

            if task.get("evidence"):
                lines.append(f"    Evidence: {task['evidence']}")
            if task.get("blocked_reason"):
                lines.append(f"    Blocked: {task['blocked_reason']}")
            for note in task.get("notes", []):
                lines.append(f"    - {note}")

        lines.extend([
            "",
            "## Notes",
            "- Tasks may be expanded but never deleted",
            "- Completed tasks must include evidence",
        ])

        try:
            md_path.write_text("\n".join(lines), encoding="utf-8")
        except Exception:
            pass  # Non-critical if markdown update fails

    def validate_args(self, args: Dict[str, Any]) -> List[str]:
        errors = []
        if not args.get("task_id"):
            errors.append("task_id is required")
        if not args.get("new_state"):
            errors.append("new_state is required")
        return errors

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "Task identifier",
                },
                "new_state": {
                    "type": "string",
                    "enum": self.VALID_STATES,
                    "description": "New task state",
                },
                "evidence": {
                    "type": "string",
                    "description": "Evidence of completion (required for completed state)",
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for blocking (required for blocked state)",
                },
                "json_path": {
                    "type": "string",
                    "description": "Path to tasks.json",
                },
            },
            "required": ["task_id", "new_state"],
        }
