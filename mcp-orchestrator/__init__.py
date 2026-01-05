"""
MCP Orchestrator - Autonomous Voice-First Cloud Operations

An AUTONOMOUS, VOICE-FIRST MCP ORCHESTRATOR that:
- Converts voice/text into executable plans
- Spawns subagents to execute tasks
- Uses skills for atomic operations
- Enforces safety via hooks
- Runs continuously UNTIL THE TASK IS ACTUALLY DONE

Core principle (NON-NEGOTIABLE):
THE SYSTEM IS NOT DONE UNTIL THE TO-DO IS DONE.
"""

__version__ = "1.0.0"
__author__ = "MCP Team"

from .core import MCPOrchestrator, WorkflowEngine, Config
from .agents import (
    AgentManager,
    PlannerAgent,
    ExecutorAgent,
    MonitorAgent,
    DebuggerAgent,
    ApprovalAgent,
    TaskManagerAgent,
)
from .hooks import StopHook, PreStepHook, PostStepHook, ApprovalHook
from .state import SessionStore, MemoryStore, AuditLogger
from .ui import VoiceHandler, TimelineHandler

__all__ = [
    # Core
    "MCPOrchestrator",
    "WorkflowEngine",
    "Config",
    # Agents
    "AgentManager",
    "PlannerAgent",
    "ExecutorAgent",
    "MonitorAgent",
    "DebuggerAgent",
    "ApprovalAgent",
    "TaskManagerAgent",
    # Hooks
    "StopHook",
    "PreStepHook",
    "PostStepHook",
    "ApprovalHook",
    # State
    "SessionStore",
    "MemoryStore",
    "AuditLogger",
    # UI
    "VoiceHandler",
    "TimelineHandler",
]
