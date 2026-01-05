"""
Verify Task Completion Skill

Verifies that all tasks in the ledger are complete.
This is CRITICAL for the stop hook to determine if termination is allowed.
"""

from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime
import json

from .base_skill import BaseSkill, SkillResult


class VerifyTaskCompletion(BaseSkill):
    """
    Skill to verify all tasks are complete.

    Per the Master Guide:
    - System CANNOT terminate until all tasks are [x]
    - Final verification task must pass
    - This is called by the stop hook

    Returns detailed completion status.
    """

    name = "verify_task_completion"
    description = "Verify that all tasks in the ledger are complete"
    required_permissions = ["task:read"]
    estimated_cost = 0.0

    async def execute(
        self,
        args: Dict[str, Any],
        context: Optional[Any] = None
    ) -> SkillResult:
        """
        Verify task completion.

        Args:
            args:
                - json_path: Path to tasks.json
                - strict: If True, blocked tasks also prevent completion
        """
        await self.pre_execute(args)

        json_path = Path(args.get("json_path", "tasks.json"))
        strict = args.get("strict", True)

        try:
            # Load current ledger
            if not json_path.exists():
                return SkillResult(
                    success=False,
                    error=f"Task ledger not found: {json_path}",
                )

            ledger = json.loads(json_path.read_text(encoding="utf-8"))
            tasks = ledger.get("tasks", [])

            # Analyze completion
            total = len(tasks)
            completed = 0
            pending = 0
            in_progress = 0
            blocked = 0

            incomplete_tasks = []
            blocked_tasks = []

            for task in tasks:
                state = task.get("state", "pending")

                if state == "completed":
                    completed += 1

                    # Verify evidence exists
                    if not task.get("evidence"):
                        incomplete_tasks.append({
                            "id": task["id"],
                            "issue": "marked complete but no evidence",
                        })
                elif state == "pending":
                    pending += 1
                    incomplete_tasks.append({
                        "id": task["id"],
                        "description": task.get("description"),
                        "state": state,
                    })
                elif state == "in_progress":
                    in_progress += 1
                    incomplete_tasks.append({
                        "id": task["id"],
                        "description": task.get("description"),
                        "state": state,
                    })
                elif state == "blocked":
                    blocked += 1
                    blocked_tasks.append({
                        "id": task["id"],
                        "description": task.get("description"),
                        "reason": task.get("blocked_reason"),
                    })

            # Determine if all complete
            all_complete = (
                completed == total and
                len(incomplete_tasks) == 0 and
                (not strict or blocked == 0)
            )

            skill_result = SkillResult(
                success=all_complete,
                data={
                    "all_complete": all_complete,
                    "total_tasks": total,
                    "completed": completed,
                    "pending": pending,
                    "in_progress": in_progress,
                    "blocked": blocked,
                    "completion_percentage": (completed / total * 100) if total > 0 else 0,
                    "incomplete_tasks": incomplete_tasks,
                    "blocked_tasks": blocked_tasks,
                    "termination_allowed": all_complete,
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

    def validate_args(self, args: Dict[str, Any]) -> List[str]:
        return []  # No required args

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "json_path": {
                    "type": "string",
                    "description": "Path to tasks.json",
                },
                "strict": {
                    "type": "boolean",
                    "description": "If True, blocked tasks prevent completion",
                    "default": True,
                },
            },
        }
