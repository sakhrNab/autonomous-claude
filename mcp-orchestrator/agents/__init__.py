"""
MCP Agents Module

Contains all subagents for the autonomous MCP orchestrator.
Each agent has ONE responsibility and follows the single-responsibility principle.

SESSION 2 additions:
- Conversation Agent: Coordinates messages, routes to planner, updates task ledger
- Decision Agent: Dynamically selects agent/skill/hook for each request
"""

# Use try/except for imports that may fail
try:
    from .base_agent import BaseAgent, AgentState, AgentResult, AgentContext
except ImportError:
    BaseAgent = AgentState = AgentResult = AgentContext = None

try:
    from .agent_manager import AgentManager
except ImportError:
    AgentManager = None

try:
    from .planner_agent import PlannerAgent
except ImportError:
    PlannerAgent = None

try:
    from .executor_agent import ExecutorAgent
except ImportError:
    ExecutorAgent = None

try:
    from .monitor_agent import MonitorAgent
except ImportError:
    MonitorAgent = None

try:
    from .debugger_agent import DebuggerAgent
except ImportError:
    DebuggerAgent = None

try:
    from .approval_agent import ApprovalAgent
except ImportError:
    ApprovalAgent = None

try:
    from .task_manager_agent import TaskManagerAgent
except ImportError:
    TaskManagerAgent = None

try:
    from .conversation_agent import ConversationAgent
except ImportError:
    ConversationAgent = None

try:
    from .decision_agent import DecisionAgent
except ImportError:
    DecisionAgent = None

__all__ = [
    "BaseAgent",
    "AgentState",
    "AgentResult",
    "AgentContext",
    "AgentManager",
    "PlannerAgent",
    "ExecutorAgent",
    "MonitorAgent",
    "DebuggerAgent",
    "ApprovalAgent",
    "TaskManagerAgent",
    # Session 2
    "ConversationAgent",
    "DecisionAgent",
]
