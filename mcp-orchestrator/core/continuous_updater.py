"""
Continuous Task Ledger Updater

Per SESSION 2 Guide:
- All agents call Task Manager after each subtask
- Stop Hook reads task ledger live
- Task Ledger updates IMMEDIATELY after any action

This module provides:
1. A decorator for automatic task ledger updates
2. A context manager for tracked operations
3. A mixin for agents to inherit continuous update behavior
"""

from datetime import datetime
from functools import wraps
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING
import asyncio

if TYPE_CHECKING:
    from ..agents.task_manager_agent import TaskManagerAgent
    from ..agents.base_agent import AgentContext


class TaskLedgerUpdater:
    """
    Continuous Task Ledger Updater.

    Ensures task ledger is updated IMMEDIATELY after any action.
    """

    def __init__(self, task_manager: "TaskManagerAgent"):
        self.task_manager = task_manager
        self.pending_updates: list = []
        self._lock = asyncio.Lock()

    async def update_task(
        self,
        task_id: str,
        new_state: str,
        evidence: Optional[str] = None,
        reason: Optional[str] = None,
        notes: Optional[str] = None
    ):
        """
        Update a task in the ledger IMMEDIATELY.

        Per SESSION 2 Guide: Task Ledger updates IMMEDIATELY after any action.
        """
        from ..agents.base_agent import AgentContext

        async with self._lock:
            context = AgentContext(
                session_id="continuous_updater",
                user_id="system",
                iteration=0,
                plan={
                    "action": "update_task",
                    "task_id": task_id,
                    "new_state": new_state,
                    "evidence": evidence,
                    "reason": reason,
                },
            )

            result = await self.task_manager.perform_step(context)

            if notes:
                notes_context = AgentContext(
                    session_id="continuous_updater",
                    user_id="system",
                    iteration=0,
                    plan={
                        "action": "add_notes",
                        "task_id": task_id,
                        "note": notes,
                    },
                )
                await self.task_manager.perform_step(notes_context)

            return result

    async def start_task(self, task_id: str, notes: Optional[str] = None):
        """Mark a task as in_progress."""
        return await self.update_task(
            task_id=task_id,
            new_state="in_progress",
            notes=notes or f"Started at {datetime.now().isoformat()}",
        )

    async def complete_task(self, task_id: str, evidence: str):
        """Mark a task as completed with evidence."""
        return await self.update_task(
            task_id=task_id,
            new_state="completed",
            evidence=evidence,
            notes=f"Completed at {datetime.now().isoformat()}",
        )

    async def block_task(self, task_id: str, reason: str):
        """Mark a task as blocked with reason."""
        return await self.update_task(
            task_id=task_id,
            new_state="blocked",
            reason=reason,
            notes=f"Blocked at {datetime.now().isoformat()}: {reason}",
        )


def with_task_update(task_id_getter: Callable[..., str]):
    """
    Decorator to automatically update task ledger after agent actions.

    Usage:
        @with_task_update(lambda ctx: ctx.plan.get('task_id'))
        async def perform_action(self, context):
            # ... action code ...
            return result

    The decorator will:
    1. Mark task as in_progress before execution
    2. Mark task as completed on success
    3. Mark task as blocked on failure
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(self, context: "AgentContext", *args, **kwargs):
            task_id = task_id_getter(context)
            updater = getattr(self, '_task_updater', None)

            if not task_id or not updater:
                return await func(self, context, *args, **kwargs)

            # Start task
            await updater.start_task(task_id)

            try:
                result = await func(self, context, *args, **kwargs)

                if result.success:
                    evidence = f"Action completed: {result.data}" if result.data else "Action completed successfully"
                    await updater.complete_task(task_id, evidence)
                else:
                    await updater.block_task(task_id, result.error or "Action failed")

                return result

            except Exception as e:
                await updater.block_task(task_id, str(e))
                raise

        return wrapper
    return decorator


class ContinuousUpdateMixin:
    """
    Mixin for agents to inherit continuous update behavior.

    Usage:
        class MyAgent(BaseAgent, ContinuousUpdateMixin):
            def __init__(self, task_manager):
                super().__init__(name="MyAgent")
                self.init_continuous_updates(task_manager)
    """

    _task_updater: Optional[TaskLedgerUpdater] = None

    def init_continuous_updates(self, task_manager: "TaskManagerAgent"):
        """Initialize continuous updates with a task manager."""
        self._task_updater = TaskLedgerUpdater(task_manager)

    async def update_task_immediately(
        self,
        task_id: str,
        new_state: str,
        evidence: Optional[str] = None,
        reason: Optional[str] = None
    ):
        """
        Update task ledger IMMEDIATELY.

        This method should be called after every significant action.
        """
        if self._task_updater:
            return await self._task_updater.update_task(
                task_id=task_id,
                new_state=new_state,
                evidence=evidence,
                reason=reason,
            )


class TaskContext:
    """
    Context manager for tracked task execution.

    Usage:
        async with TaskContext(updater, "task_123") as ctx:
            # Do work here
            ctx.add_note("Progress update")
            result = await some_operation()

        # Task automatically marked complete/failed based on exceptions
    """

    def __init__(
        self,
        updater: TaskLedgerUpdater,
        task_id: str,
        auto_complete: bool = True
    ):
        self.updater = updater
        self.task_id = task_id
        self.auto_complete = auto_complete
        self.notes: list = []
        self.success = False
        self.evidence = ""

    async def __aenter__(self):
        await self.updater.start_task(self.task_id)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self.updater.block_task(
                self.task_id,
                f"Error: {exc_val}"
            )
        elif self.auto_complete:
            await self.updater.complete_task(
                self.task_id,
                self.evidence or "Task completed via context manager"
            )
        return False

    def add_note(self, note: str):
        """Add a note to track progress."""
        self.notes.append(note)

    def set_evidence(self, evidence: str):
        """Set the completion evidence."""
        self.evidence = evidence


async def ensure_continuous_updates(
    agents: list,
    task_manager: "TaskManagerAgent"
):
    """
    Configure all agents to use continuous task ledger updates.

    Per SESSION 2 Guide: All agents call Task Manager after each subtask.
    """
    updater = TaskLedgerUpdater(task_manager)

    for agent in agents:
        if hasattr(agent, '_task_updater'):
            agent._task_updater = updater
        elif hasattr(agent, 'task_manager'):
            agent.task_manager = task_manager

    return updater
