"""
Base Agent class for all subagents.

All agents inherit from this class and implement the perform_step method.
Agents NEVER decide termination - that is the stop hook's responsibility.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class AgentState(Enum):
    """Possible states for an agent."""
    IDLE = "idle"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentResult:
    """Result from an agent step execution."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    artifacts: List[str] = field(default_factory=list)
    next_action: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "artifacts": self.artifacts,
            "next_action": self.next_action,
            "metadata": self.metadata,
        }


@dataclass
class AgentContext:
    """Context passed to agents during execution."""
    session_id: str
    user_id: str
    iteration: int
    plan: Optional[Dict[str, Any]] = None
    previous_results: List[AgentResult] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    budget_remaining: float = 100.0
    time_started: datetime = field(default_factory=datetime.now)


class BaseAgent(ABC):
    """
    Base class for all agents in the MCP system.

    Each agent MUST:
    - Have ONE responsibility
    - Implement perform_step()
    - Return structured results
    - NEVER decide termination

    The stop hook decides termination, not agents.
    """

    def __init__(self, agent_id: Optional[str] = None, name: str = "BaseAgent"):
        self.agent_id = agent_id or str(uuid.uuid4())
        self.name = name
        self.state = AgentState.IDLE
        self.iteration_count = 0
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self._logs: List[Dict[str, Any]] = []

    @abstractmethod
    async def perform_step(self, context: AgentContext) -> AgentResult:
        """
        Perform a single step of the agent's work.

        This is the ONLY method that subclasses must implement.
        The agent does its work, then returns a result.
        It does NOT decide if it should continue or stop.

        Args:
            context: The current execution context

        Returns:
            AgentResult with the outcome of this step
        """
        pass

    def log(self, level: str, message: str, data: Optional[Dict[str, Any]] = None):
        """Log a message from this agent."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent_id": self.agent_id,
            "agent_name": self.name,
            "level": level,
            "message": message,
            "data": data or {},
        }
        self._logs.append(log_entry)
        self.last_activity = datetime.now()

    def get_logs(self) -> List[Dict[str, Any]]:
        """Get all logs from this agent."""
        return self._logs.copy()

    def clear_logs(self):
        """Clear the agent's logs."""
        self._logs = []

    async def initialize(self, context: AgentContext):
        """Initialize the agent before execution. Override if needed."""
        self.state = AgentState.RUNNING
        self.log("info", f"Agent {self.name} initialized", {"session_id": context.session_id})

    async def cleanup(self):
        """Cleanup after agent execution. Override if needed."""
        self.state = AgentState.IDLE
        self.log("info", f"Agent {self.name} cleanup complete")

    def to_dict(self) -> Dict[str, Any]:
        """Convert agent state to dictionary."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "state": self.state.value,
            "iteration_count": self.iteration_count,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
        }
