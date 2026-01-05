"""
MCP Agents Module

Contains all subagents for the autonomous MCP orchestrator.
Each agent has ONE responsibility and follows the single-responsibility principle.

SESSION 2 additions:
- Conversation Agent: Coordinates messages, routes to planner, updates task ledger
- Decision Agent: Dynamically selects agent/skill/hook for each request
"""

from .base_agent import BaseAgent, AgentState, AgentResult, AgentContext
from .agent_manager import AgentManager
from .planner_agent import PlannerAgent
from .executor_agent import ExecutorAgent
from .monitor_agent import MonitorAgent
from .debugger_agent import DebuggerAgent
from .approval_agent import ApprovalAgent
from .task_manager_agent import TaskManagerAgent
from .conversation_agent import ConversationAgent
from .decision_agent import DecisionAgent

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
