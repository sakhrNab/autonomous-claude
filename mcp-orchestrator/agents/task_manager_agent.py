"""
Task Manager Agent

RESPONSIBILITY: Own the Task Ledger

Per the AUTONOMOUS MCP MASTER GUIDE:
- ONLY the Task Manager Agent may mark tasks complete
- ONLY the Task Manager Agent may unblock tasks
- ONLY the Task Manager Agent may approve task evidence
- All other agents MUST REQUEST updates

This agent is the gatekeeper of task state transitions.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import re

from .base_agent import BaseAgent, AgentContext, AgentResult


class TaskState(Enum):
    """Task states as defined in the Master Guide."""
    PENDING = "pending"        # [ ]
    IN_PROGRESS = "in_progress"  # [~]
    COMPLETED = "completed"    # [x]
    BLOCKED = "blocked"        # [!]


@dataclass
class Task:
    """A single task in the task ledger."""
    id: str
    description: str
    state: TaskState
    evidence: Optional[str] = None
    notes: List[str] = None
    created_at: datetime = None
    updated_at: datetime = None
    blocked_reason: Optional[str] = None

    def __post_init__(self):
        if self.notes is None:
            self.notes = []
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()


class TaskManagerAgent(BaseAgent):
    """
    Task Manager Agent - Owns the Task Ledger.

    This is a REQUIRED agent per the Master Guide.

    Responsibilities:
    - Own the Task Ledger
    - Validate task transitions
    - Prevent premature completion

    ONLY this agent may:
    - Mark tasks complete
    - Unblock tasks
    - Approve task evidence
    """

    def __init__(self, ledger_path: str = "to-do.md", tasks_json_path: str = "tasks.json"):
        super().__init__(name="TaskManagerAgent")
        self.ledger_path = Path(ledger_path)
        self.tasks_json_path = Path(tasks_json_path)
        self.tasks: Dict[str, Task] = {}
        self.session_id: Optional[str] = None

    async def perform_step(self, context: AgentContext) -> AgentResult:
        """
        Perform task management operations.

        The Task Manager responds to requests from other agents
        to update task states.
        """
        self.iteration_count += 1
        self.session_id = context.session_id

        # Check what action is requested
        action = context.plan.get("action") if context.plan else None

        if action == "create_ledger":
            return await self._create_ledger(context)
        elif action == "update_task":
            return await self._update_task(context)
        elif action == "verify_completion":
            return await self._verify_all_complete(context)
        elif action == "list_remaining":
            return await self._list_remaining(context)
        elif action == "add_notes":
            return await self._add_notes(context)
        else:
            # Default: check current state
            return await self._get_status(context)

    async def _create_ledger(self, context: AgentContext) -> AgentResult:
        """Create the initial task ledger."""
        tasks = context.plan.get("tasks", [])

        for i, task_desc in enumerate(tasks):
            task_id = f"task_{i+1}"
            self.tasks[task_id] = Task(
                id=task_id,
                description=task_desc,
                state=TaskState.PENDING,
            )

        await self._write_ledger()
        await self._write_json()

        self.log("info", "Task ledger created", {"task_count": len(tasks)})

        return AgentResult(
            success=True,
            data={"tasks_created": len(tasks)},
            artifacts=[str(self.ledger_path), str(self.tasks_json_path)],
        )

    async def _update_task(self, context: AgentContext) -> AgentResult:
        """
        Update a task's state.

        Validates transitions and requires evidence for completion.
        """
        task_id = context.plan.get("task_id")
        new_state = context.plan.get("new_state")
        evidence = context.plan.get("evidence")
        reason = context.plan.get("reason")

        if task_id not in self.tasks:
            return AgentResult(
                success=False,
                error=f"Task {task_id} not found",
            )

        task = self.tasks[task_id]

        # Validate transition
        if new_state == TaskState.COMPLETED.value:
            if not evidence:
                return AgentResult(
                    success=False,
                    error="Cannot mark task complete without evidence",
                )
            # Validate evidence
            if not self._validate_evidence(evidence):
                return AgentResult(
                    success=False,
                    error="Evidence validation failed",
                )
            task.evidence = evidence

        if new_state == TaskState.BLOCKED.value:
            if not reason:
                return AgentResult(
                    success=False,
                    error="Blocked tasks require a reason",
                )
            task.blocked_reason = reason

        # Apply transition
        task.state = TaskState(new_state)
        task.updated_at = datetime.now()

        await self._write_ledger()
        await self._write_json()

        self.log("info", f"Task {task_id} updated to {new_state}")

        return AgentResult(
            success=True,
            data={
                "task_id": task_id,
                "new_state": new_state,
            },
        )

    async def _verify_all_complete(self, context: AgentContext) -> AgentResult:
        """
        Verify that ALL tasks are complete.

        This is called by the stop hook to determine if termination is allowed.
        Per the Master Guide: System CANNOT terminate until all tasks are [x].
        """
        incomplete = []
        blocked = []

        for task_id, task in self.tasks.items():
            if task.state == TaskState.BLOCKED:
                blocked.append(task_id)
            elif task.state != TaskState.COMPLETED:
                incomplete.append(task_id)

        all_complete = len(incomplete) == 0 and len(blocked) == 0

        self.log("info", "Task completion check", {
            "all_complete": all_complete,
            "incomplete": incomplete,
            "blocked": blocked,
        })

        return AgentResult(
            success=all_complete,
            data={
                "all_complete": all_complete,
                "incomplete_count": len(incomplete),
                "blocked_count": len(blocked),
                "incomplete_tasks": incomplete,
                "blocked_tasks": blocked,
            },
        )

    async def _list_remaining(self, context: AgentContext) -> AgentResult:
        """List all remaining (incomplete) tasks."""
        remaining = []

        for task_id, task in self.tasks.items():
            if task.state != TaskState.COMPLETED:
                remaining.append({
                    "id": task_id,
                    "description": task.description,
                    "state": task.state.value,
                })

        return AgentResult(
            success=True,
            data={"remaining_tasks": remaining, "count": len(remaining)},
        )

    async def _add_notes(self, context: AgentContext) -> AgentResult:
        """Add notes to a task."""
        task_id = context.plan.get("task_id")
        note = context.plan.get("note")

        if task_id not in self.tasks:
            return AgentResult(
                success=False,
                error=f"Task {task_id} not found",
            )

        self.tasks[task_id].notes.append(note)
        self.tasks[task_id].updated_at = datetime.now()

        await self._write_ledger()
        await self._write_json()

        return AgentResult(
            success=True,
            data={"task_id": task_id, "note_added": True},
        )

    async def _get_status(self, context: AgentContext) -> AgentResult:
        """Get current status of all tasks."""
        status = {
            "total": len(self.tasks),
            "pending": 0,
            "in_progress": 0,
            "completed": 0,
            "blocked": 0,
        }

        for task in self.tasks.values():
            status[task.state.value] += 1

        return AgentResult(
            success=True,
            data=status,
        )

    def _validate_evidence(self, evidence: str) -> bool:
        """
        Validate that evidence is sufficient for completion.

        Evidence must reference artifacts or verifiable outcomes.
        """
        # Basic validation - evidence must be non-empty and substantial
        if not evidence or len(evidence) < 10:
            return False
        return True

    async def _write_ledger(self):
        """Write the task ledger to to-do.md."""
        state_symbols = {
            TaskState.PENDING: "[ ]",
            TaskState.IN_PROGRESS: "[~]",
            TaskState.COMPLETED: "[x]",
            TaskState.BLOCKED: "[!]",
        }

        lines = [
            "# Task Ledger",
            f"Session: {self.session_id or 'unknown'}",
            f"Updated: {datetime.now().isoformat()}",
            "",
            "## Core Tasks",
        ]

        for task_id, task in self.tasks.items():
            symbol = state_symbols[task.state]
            lines.append(f"{symbol} {task.id}: {task.description}")

            if task.evidence:
                lines.append(f"    Evidence: {task.evidence}")
            if task.blocked_reason:
                lines.append(f"    Blocked: {task.blocked_reason}")
            for note in task.notes:
                lines.append(f"    - {note}")

        lines.extend([
            "",
            "## Notes",
            "- Tasks may be expanded but never deleted",
            "- Completed tasks must include evidence",
        ])

        content = "\n".join(lines)
        self.ledger_path.write_text(content, encoding="utf-8")

    async def _write_json(self):
        """Write tasks to JSON for machine reading."""
        data = {
            "session_id": self.session_id,
            "updated_at": datetime.now().isoformat(),
            "tasks": [
                {
                    "id": task.id,
                    "description": task.description,
                    "state": task.state.value,
                    "evidence": task.evidence,
                    "notes": task.notes,
                    "blocked_reason": task.blocked_reason,
                    "created_at": task.created_at.isoformat() if task.created_at else None,
                    "updated_at": task.updated_at.isoformat() if task.updated_at else None,
                }
                for task in self.tasks.values()
            ],
        }

        self.tasks_json_path.write_text(
            json.dumps(data, indent=2),
            encoding="utf-8"
        )

    async def load_from_file(self):
        """Load task ledger from existing file."""
        if self.tasks_json_path.exists():
            data = json.loads(self.tasks_json_path.read_text(encoding="utf-8"))
            self.session_id = data.get("session_id")

            for task_data in data.get("tasks", []):
                self.tasks[task_data["id"]] = Task(
                    id=task_data["id"],
                    description=task_data["description"],
                    state=TaskState(task_data["state"]),
                    evidence=task_data.get("evidence"),
                    notes=task_data.get("notes", []),
                    blocked_reason=task_data.get("blocked_reason"),
                )
