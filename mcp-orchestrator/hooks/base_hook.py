"""
Base Hook class for all hooks.

Hooks run OUTSIDE agent logic to enforce safety and autonomy.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class HookAction(Enum):
    """Actions a hook can return."""
    CONTINUE = "continue"    # Keep going
    TERMINATE = "terminate"  # Stop execution
    ESCALATE = "escalate"    # Pause and ask human
    SKIP = "skip"            # Skip this step
    RETRY = "retry"          # Retry the step


@dataclass
class HookResult:
    """Result from a hook execution."""
    action: HookAction
    reason: str
    confidence: float = 1.0
    data: Dict[str, Any] = field(default_factory=dict)
    next_expected_state: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action.value,
            "reason": self.reason,
            "confidence": self.confidence,
            "data": self.data,
            "next_expected_state": self.next_expected_state,
            "metadata": self.metadata,
        }


@dataclass
class HookContext:
    """Context provided to hooks."""
    session_id: str
    agent_id: str
    iteration: int
    elapsed_time_seconds: float
    logs: List[str] = field(default_factory=list)
    test_results: Optional[Dict[str, Any]] = None
    permissions: List[str] = field(default_factory=list)
    budget_spent: float = 0.0
    budget_limit: float = 100.0
    task_ledger_path: str = "tasks.json"


class BaseHook(ABC):
    """
    Base class for all hooks.

    Hooks are safety and control mechanisms that:
    - Run outside agent logic
    - Cannot be bypassed by agents
    - Control the flow of execution
    """

    name: str = "BaseHook"
    description: str = "Base hook class"

    def __init__(self):
        self.execution_count = 0
        self.last_execution = None
        self._history: List[HookResult] = []

    @abstractmethod
    async def execute(self, context: HookContext) -> HookResult:
        """
        Execute the hook.

        Args:
            context: Current execution context

        Returns:
            HookResult with action decision
        """
        pass

    def record_result(self, result: HookResult):
        """Record the result for auditing."""
        self._history.append(result)
        self.execution_count += 1
        self.last_execution = datetime.now()

    def get_history(self) -> List[HookResult]:
        """Get execution history."""
        return self._history.copy()

    def to_dict(self) -> Dict[str, Any]:
        """Convert hook info to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "execution_count": self.execution_count,
            "last_execution": self.last_execution.isoformat() if self.last_execution else None,
        }
