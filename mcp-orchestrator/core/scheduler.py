"""
Scheduler Integration

Handles scheduled triggers for workflows and MCPs.

Per SESSION 2 Guide:
- Messages or scheduled triggers automatically invoke workflows/MCPs in Cloud Code
- Supports cron-like scheduling
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import asyncio


class ScheduleType(Enum):
    """Types of schedules."""
    ONCE = "once"
    INTERVAL = "interval"
    CRON = "cron"
    DAILY = "daily"
    WEEKLY = "weekly"


@dataclass
class ScheduledTask:
    """A scheduled task."""
    task_id: str
    name: str
    schedule_type: ScheduleType
    target_type: str  # "workflow", "mcp", "skill"
    target_name: str
    payload: Dict[str, Any]
    enabled: bool = True

    # Timing
    next_run: Optional[datetime] = None
    last_run: Optional[datetime] = None
    interval_seconds: Optional[int] = None
    cron_expression: Optional[str] = None

    # Context
    user_id: Optional[str] = None
    session_id: Optional[str] = None

    # Stats
    run_count: int = 0
    success_count: int = 0
    failure_count: int = 0

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "schedule_type": self.schedule_type.value,
            "target_type": self.target_type,
            "target_name": self.target_name,
            "payload": self.payload,
            "enabled": self.enabled,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "interval_seconds": self.interval_seconds,
            "run_count": self.run_count,
            "success_count": self.success_count,
        }


class Scheduler:
    """
    Scheduler - Handles scheduled task execution.

    This scheduler:
    - Manages scheduled tasks
    - Triggers workflows/MCPs at specified times
    - Supports various schedule types (once, interval, cron)
    - Integrates with Cloud Code adapter
    """

    def __init__(self, cloud_code_adapter=None):
        self.cloud_code_adapter = cloud_code_adapter
        self.tasks: Dict[str, ScheduledTask] = {}
        self.running = False
        self._task_loop: Optional[asyncio.Task] = None
        self.execution_callbacks: List[Callable] = []

    def schedule_task(
        self,
        name: str,
        target_type: str,
        target_name: str,
        payload: Dict[str, Any],
        schedule_type: ScheduleType,
        run_at: Optional[datetime] = None,
        interval_seconds: Optional[int] = None,
        cron_expression: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> ScheduledTask:
        """Schedule a new task."""
        import uuid
        task_id = str(uuid.uuid4())

        # Calculate next run time
        if schedule_type == ScheduleType.ONCE:
            next_run = run_at or datetime.now()
        elif schedule_type == ScheduleType.INTERVAL:
            next_run = datetime.now() + timedelta(seconds=interval_seconds or 60)
        elif schedule_type == ScheduleType.DAILY:
            next_run = run_at or datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1)
        elif schedule_type == ScheduleType.WEEKLY:
            next_run = run_at or datetime.now() + timedelta(weeks=1)
        else:
            next_run = run_at or datetime.now()

        task = ScheduledTask(
            task_id=task_id,
            name=name,
            schedule_type=schedule_type,
            target_type=target_type,
            target_name=target_name,
            payload=payload,
            next_run=next_run,
            interval_seconds=interval_seconds,
            cron_expression=cron_expression,
            user_id=user_id,
            session_id=session_id,
        )

        self.tasks[task_id] = task
        return task

    def schedule_workflow(
        self,
        name: str,
        workflow_name: str,
        input_data: Dict[str, Any],
        run_at: datetime,
        repeat_interval: Optional[int] = None
    ) -> ScheduledTask:
        """Schedule a workflow execution."""
        schedule_type = ScheduleType.INTERVAL if repeat_interval else ScheduleType.ONCE

        return self.schedule_task(
            name=name,
            target_type="workflow",
            target_name=workflow_name,
            payload=input_data,
            schedule_type=schedule_type,
            run_at=run_at,
            interval_seconds=repeat_interval,
        )

    def schedule_mcp(
        self,
        name: str,
        mcp_name: str,
        action: str,
        params: Dict[str, Any],
        run_at: datetime,
        repeat_interval: Optional[int] = None
    ) -> ScheduledTask:
        """Schedule an MCP trigger."""
        schedule_type = ScheduleType.INTERVAL if repeat_interval else ScheduleType.ONCE

        return self.schedule_task(
            name=name,
            target_type="mcp",
            target_name=mcp_name,
            payload={"action": action, "params": params},
            schedule_type=schedule_type,
            run_at=run_at,
            interval_seconds=repeat_interval,
        )

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a scheduled task."""
        if task_id in self.tasks:
            self.tasks[task_id].enabled = False
            return True
        return False

    def delete_task(self, task_id: str) -> bool:
        """Delete a scheduled task."""
        if task_id in self.tasks:
            del self.tasks[task_id]
            return True
        return False

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """Get a scheduled task."""
        return self.tasks.get(task_id)

    def get_pending_tasks(self) -> List[ScheduledTask]:
        """Get all tasks that should run now or soon."""
        now = datetime.now()
        return [
            task for task in self.tasks.values()
            if task.enabled and task.next_run and task.next_run <= now
        ]

    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """Get all scheduled tasks."""
        return [task.to_dict() for task in self.tasks.values()]

    async def start(self):
        """Start the scheduler loop."""
        if self.running:
            return

        self.running = True
        self._task_loop = asyncio.create_task(self._scheduler_loop())

    async def stop(self):
        """Stop the scheduler loop."""
        self.running = False
        if self._task_loop:
            self._task_loop.cancel()
            try:
                await self._task_loop
            except asyncio.CancelledError:
                pass

    async def _scheduler_loop(self):
        """Main scheduler loop."""
        while self.running:
            try:
                # Get pending tasks
                pending = self.get_pending_tasks()

                # Execute pending tasks
                for task in pending:
                    asyncio.create_task(self._execute_task(task))

                # Sleep before next check
                await asyncio.sleep(1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log error but continue
                await asyncio.sleep(5)

    async def _execute_task(self, task: ScheduledTask):
        """Execute a scheduled task."""
        try:
            task.last_run = datetime.now()
            task.run_count += 1

            # Execute based on target type
            if task.target_type == "workflow" and self.cloud_code_adapter:
                result = await self.cloud_code_adapter.trigger_workflow(
                    workflow_name=task.target_name,
                    input_data=task.payload,
                    session_id=task.session_id,
                )
                success = result.success
            elif task.target_type == "mcp" and self.cloud_code_adapter:
                result = await self.cloud_code_adapter.trigger_mcp(
                    mcp_name=task.target_name,
                    action=task.payload.get("action", "execute"),
                    params=task.payload.get("params", {}),
                    session_id=task.session_id,
                )
                success = result.success
            else:
                # Generic execution
                success = True

            if success:
                task.success_count += 1
            else:
                task.failure_count += 1

            # Update next run time
            self._update_next_run(task)

            # Notify callbacks
            for callback in self.execution_callbacks:
                try:
                    callback({
                        "task_id": task.task_id,
                        "name": task.name,
                        "success": success,
                        "run_count": task.run_count,
                    })
                except Exception:
                    pass

        except Exception as e:
            task.failure_count += 1
            self._update_next_run(task)

    def _update_next_run(self, task: ScheduledTask):
        """Update the next run time for a task."""
        if task.schedule_type == ScheduleType.ONCE:
            task.enabled = False
            task.next_run = None
        elif task.schedule_type == ScheduleType.INTERVAL:
            task.next_run = datetime.now() + timedelta(seconds=task.interval_seconds or 60)
        elif task.schedule_type == ScheduleType.DAILY:
            task.next_run = datetime.now() + timedelta(days=1)
        elif task.schedule_type == ScheduleType.WEEKLY:
            task.next_run = datetime.now() + timedelta(weeks=1)

    def add_execution_callback(self, callback: Callable):
        """Add a callback for task execution events."""
        self.execution_callbacks.append(callback)

    def get_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics."""
        total_tasks = len(self.tasks)
        enabled_tasks = len([t for t in self.tasks.values() if t.enabled])
        total_runs = sum(t.run_count for t in self.tasks.values())
        total_successes = sum(t.success_count for t in self.tasks.values())

        return {
            "total_tasks": total_tasks,
            "enabled_tasks": enabled_tasks,
            "total_runs": total_runs,
            "total_successes": total_successes,
            "success_rate": total_successes / total_runs if total_runs > 0 else 0,
            "running": self.running,
        }
