"""
MCP Orchestrator Core Module

The brain of the autonomous MCP system.

SESSION 2 additions:
- CloudCodeAdapter: Handles remote Cloud Code triggers
- Scheduler: Scheduled task execution
- ContinuousUpdater: Ensures task ledger updates IMMEDIATELY
"""

from .orchestrator import MCPOrchestrator
from .workflow_engine import WorkflowEngine
from .config import Config
from .cloud_code_adapter import CloudCodeAdapter, CloudCodeProvider
from .scheduler import Scheduler, ScheduledTask, ScheduleType
from .continuous_updater import (
    TaskLedgerUpdater,
    ContinuousUpdateMixin,
    TaskContext,
    with_task_update,
    ensure_continuous_updates,
)

__all__ = [
    "MCPOrchestrator",
    "WorkflowEngine",
    "Config",
    # Session 2
    "CloudCodeAdapter",
    "CloudCodeProvider",
    "Scheduler",
    "ScheduledTask",
    "ScheduleType",
    # Continuous updates
    "TaskLedgerUpdater",
    "ContinuousUpdateMixin",
    "TaskContext",
    "with_task_update",
    "ensure_continuous_updates",
]
