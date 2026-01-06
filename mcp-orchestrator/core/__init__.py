"""
MCP Orchestrator Core Module

The brain of the autonomous MCP system.

SESSION 2 additions:
- CloudCodeAdapter: Handles remote Cloud Code triggers
- Scheduler: Scheduled task execution
- ContinuousUpdater: Ensures task ledger updates IMMEDIATELY
"""

# Use try/except for imports that may fail due to circular imports
# This allows main_orchestrator to be imported independently
try:
    from .orchestrator import MCPOrchestrator
except ImportError:
    MCPOrchestrator = None

try:
    from .workflow_engine import WorkflowEngine
except ImportError:
    WorkflowEngine = None

try:
    from .config import Config
except ImportError:
    Config = None

try:
    from .cloud_code_adapter import CloudCodeAdapter, CloudCodeProvider
except ImportError:
    CloudCodeAdapter = None
    CloudCodeProvider = None

try:
    from .scheduler import Scheduler, ScheduledTask, ScheduleType
except ImportError:
    Scheduler = None
    ScheduledTask = None
    ScheduleType = None

try:
    from .continuous_updater import (
        TaskLedgerUpdater,
        ContinuousUpdateMixin,
        TaskContext,
        with_task_update,
        ensure_continuous_updates,
    )
except ImportError:
    TaskLedgerUpdater = None
    ContinuousUpdateMixin = None
    TaskContext = None
    with_task_update = None
    ensure_continuous_updates = None

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
