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

Usage as a library:
    from mcp_orchestrator import AutonomousOperator

    operator = AutonomousOperator(project_path="/path/to/project")
    result = await operator.execute("Build a REST API for user management")

    # result will contain:
    # - promise: "<Promise>DONE</Promise>" or "<Promise>BLOCKED: reason</Promise>"
    # - steps_completed: number of steps completed
    # - results: detailed results from each step
"""

__version__ = "1.0.0"
__author__ = "MCP Team"

# Legacy imports
try:
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
except ImportError:
    # Some legacy modules may not exist
    pass

# New Autonomous Operator imports
from .autonomous_operator import AutonomousOperator, ExecutionResult
from .core.source_of_truth import SourceOfTruth, get_source_of_truth
from .core.execution_engine import ExecutionEngine, get_execution_engine
from .agents.planning_agent import PlanningAgent, get_planning_agent, ExecutionPlan
from .hooks.hook_system import HookSystem, get_hook_system, Hook, HookTrigger
from .core.capability_creator import CapabilityCreator, get_capability_creator

__all__ = [
    # New Autonomous Operator (primary API)
    "AutonomousOperator",
    "ExecutionResult",
    "SourceOfTruth",
    "get_source_of_truth",
    "ExecutionEngine",
    "get_execution_engine",
    "PlanningAgent",
    "get_planning_agent",
    "ExecutionPlan",
    "HookSystem",
    "get_hook_system",
    "Hook",
    "HookTrigger",
    "CapabilityCreator",
    "get_capability_creator",
    # Legacy Core
    "MCPOrchestrator",
    "WorkflowEngine",
    "Config",
    # Legacy Agents
    "AgentManager",
    "PlannerAgent",
    "ExecutorAgent",
    "MonitorAgent",
    "DebuggerAgent",
    "ApprovalAgent",
    "TaskManagerAgent",
    # Legacy Hooks
    "StopHook",
    "PreStepHook",
    "PostStepHook",
    "ApprovalHook",
    # Legacy State
    "SessionStore",
    "MemoryStore",
    "AuditLogger",
    # Legacy UI
    "VoiceHandler",
    "TimelineHandler",
]
