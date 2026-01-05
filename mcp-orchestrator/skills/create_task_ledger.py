"""
Create Task Ledger Skill

Creates the initial task ledger for a session.
Per the Master Guide, this is a MANDATORY skill.
"""

from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime
import json

from .base_skill import BaseSkill, SkillResult


class CreateTaskLedger(BaseSkill):
    """
    Skill to create the initial task ledger.

    The Task Ledger is:
    - Created at the START of execution
    - The SINGLE SOURCE OF TRUTH for progress
    - Used by the stop hook to determine termination
    """

    name = "create_task_ledger"
    description = "Create the initial task ledger for a session"
    required_permissions = ["task:write"]
    estimated_cost = 0.0

    async def execute(
        self,
        args: Dict[str, Any],
        context: Optional[Any] = None
    ) -> SkillResult:
        """
        Create the task ledger.

        Args:
            args:
                - session_id: Session identifier
                - tasks: List of task descriptions
                - ledger_path: Path for to-do.md (default: to-do.md)
                - json_path: Path for tasks.json (default: tasks.json)
        """
        await self.pre_execute(args)

        session_id = args.get("session_id", "session-001")
        tasks = args.get("tasks", [])
        ledger_path = Path(args.get("ledger_path", "to-do.md"))
        json_path = Path(args.get("json_path", "tasks.json"))

        if not tasks:
            return SkillResult(
                success=False,
                error="At least one task is required",
            )

        try:
            # Create markdown ledger
            md_content = self._generate_markdown(session_id, tasks)
            ledger_path.write_text(md_content, encoding="utf-8")

            # Create JSON ledger
            json_content = self._generate_json(session_id, tasks)
            json_path.write_text(json.dumps(json_content, indent=2), encoding="utf-8")

            skill_result = SkillResult(
                success=True,
                data={
                    "session_id": session_id,
                    "task_count": len(tasks),
                    "ledger_path": str(ledger_path),
                    "json_path": str(json_path),
                },
                artifacts=[str(ledger_path), str(json_path)],
                cost=0.0,
            )

        except Exception as e:
            skill_result = SkillResult(
                success=False,
                error=str(e),
            )

        await self.post_execute(skill_result)
        return skill_result

    def _generate_markdown(self, session_id: str, tasks: List[str]) -> str:
        """Generate markdown task ledger."""
        lines = [
            "# Task Ledger",
            f"Session: {session_id}",
            f"Created: {datetime.now().isoformat()}",
            "",
            "## Core Tasks",
        ]

        for i, task in enumerate(tasks):
            lines.append(f"[ ] {i+1}. {task}")

        lines.extend([
            "",
            "## Notes",
            "- Tasks may be expanded but never deleted",
            "- Completed tasks must include evidence",
        ])

        return "\n".join(lines)

    def _generate_json(self, session_id: str, tasks: List[str]) -> Dict[str, Any]:
        """Generate JSON task ledger."""
        return {
            "session_id": session_id,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "tasks": [
                {
                    "id": f"task_{i+1}",
                    "description": task,
                    "state": "pending",
                    "evidence": None,
                    "notes": [],
                    "created_at": datetime.now().isoformat(),
                }
                for i, task in enumerate(tasks)
            ],
        }

    def validate_args(self, args: Dict[str, Any]) -> List[str]:
        errors = []
        if not args.get("tasks"):
            errors.append("tasks list is required")
        return errors

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Session identifier",
                },
                "tasks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of task descriptions",
                },
                "ledger_path": {
                    "type": "string",
                    "description": "Path for to-do.md",
                },
                "json_path": {
                    "type": "string",
                    "description": "Path for tasks.json",
                },
            },
            "required": ["tasks"],
        }
