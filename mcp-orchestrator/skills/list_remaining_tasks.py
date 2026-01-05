"""
List Remaining Tasks Skill

Lists all incomplete tasks in the ledger.
"""

from typing import Any, Dict, List, Optional
from pathlib import Path
import json

from .base_skill import BaseSkill, SkillResult


class ListRemainingTasks(BaseSkill):
    """
    Skill to list all remaining (incomplete) tasks.

    Returns tasks that are:
    - pending
    - in_progress
    - blocked (with reasons)
    """

    name = "list_remaining_tasks"
    description = "List all incomplete tasks in the ledger"
    required_permissions = ["task:read"]
    estimated_cost = 0.0

    async def execute(
        self,
        args: Dict[str, Any],
        context: Optional[Any] = None
    ) -> SkillResult:
        """
        List remaining tasks.

        Args:
            args:
                - json_path: Path to tasks.json
                - include_blocked: Include blocked tasks (default: True)
                - include_in_progress: Include in-progress tasks (default: True)
        """
        await self.pre_execute(args)

        json_path = Path(args.get("json_path", "tasks.json"))
        include_blocked = args.get("include_blocked", True)
        include_in_progress = args.get("include_in_progress", True)

        try:
            # Load current ledger
            if not json_path.exists():
                return SkillResult(
                    success=False,
                    error=f"Task ledger not found: {json_path}",
                )

            ledger = json.loads(json_path.read_text(encoding="utf-8"))
            tasks = ledger.get("tasks", [])

            remaining = []
            for task in tasks:
                state = task.get("state", "pending")

                if state == "completed":
                    continue

                if state == "pending":
                    remaining.append({
                        "id": task["id"],
                        "description": task.get("description"),
                        "state": state,
                        "priority": "high",
                    })
                elif state == "in_progress" and include_in_progress:
                    remaining.append({
                        "id": task["id"],
                        "description": task.get("description"),
                        "state": state,
                        "priority": "active",
                    })
                elif state == "blocked" and include_blocked:
                    remaining.append({
                        "id": task["id"],
                        "description": task.get("description"),
                        "state": state,
                        "blocked_reason": task.get("blocked_reason"),
                        "priority": "blocked",
                    })

            # Sort by priority
            priority_order = {"active": 0, "high": 1, "blocked": 2}
            remaining.sort(key=lambda x: priority_order.get(x.get("priority", "high"), 1))

            skill_result = SkillResult(
                success=True,
                data={
                    "remaining_count": len(remaining),
                    "remaining_tasks": remaining,
                    "next_task": remaining[0] if remaining else None,
                    "has_blocked": any(t["state"] == "blocked" for t in remaining),
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
                "include_blocked": {
                    "type": "boolean",
                    "description": "Include blocked tasks",
                    "default": True,
                },
                "include_in_progress": {
                    "type": "boolean",
                    "description": "Include in-progress tasks",
                    "default": True,
                },
            },
        }
