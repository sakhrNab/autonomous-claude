"""
Append Task Notes Skill

Adds notes to a task in the ledger.
"""

from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime
import json

from .base_skill import BaseSkill, SkillResult


class AppendTaskNotes(BaseSkill):
    """
    Skill to append notes to a task.

    Notes can include:
    - Progress updates
    - Issues encountered
    - References to artifacts
    - Debug information
    """

    name = "append_task_notes"
    description = "Add notes to a task in the ledger"
    required_permissions = ["task:write"]
    estimated_cost = 0.0

    async def execute(
        self,
        args: Dict[str, Any],
        context: Optional[Any] = None
    ) -> SkillResult:
        """
        Append a note to a task.

        Args:
            args:
                - task_id: Task identifier
                - note: Note content
                - json_path: Path to tasks.json
        """
        await self.pre_execute(args)

        task_id = args.get("task_id")
        note = args.get("note")
        json_path = Path(args.get("json_path", "tasks.json"))

        if not note:
            return SkillResult(
                success=False,
                error="note is required",
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

                    # Initialize notes if not present
                    if "notes" not in task:
                        task["notes"] = []

                    # Add timestamped note
                    timestamped_note = f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {note}"
                    task["notes"].append(timestamped_note)
                    task["updated_at"] = datetime.now().isoformat()
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

            skill_result = SkillResult(
                success=True,
                data={
                    "task_id": task_id,
                    "note_added": True,
                    "note_count": len([t for t in ledger["tasks"] if t["id"] == task_id][0].get("notes", [])),
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
        errors = []
        if not args.get("task_id"):
            errors.append("task_id is required")
        if not args.get("note"):
            errors.append("note is required")
        return errors

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "Task identifier",
                },
                "note": {
                    "type": "string",
                    "description": "Note content to append",
                },
                "json_path": {
                    "type": "string",
                    "description": "Path to tasks.json",
                },
            },
            "required": ["task_id", "note"],
        }
