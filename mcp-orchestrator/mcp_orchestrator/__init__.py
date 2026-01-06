"""
MCP Orchestrator SDK

Use this SDK to integrate the autonomous operator into your projects.

Installation:
    pip install mcp-orchestrator
    # or from source:
    pip install -e /path/to/mcp-orchestrator

Usage:
    from mcp_orchestrator import Orchestrator

    # Initialize
    orchestrator = Orchestrator(project_path="/path/to/your/project")

    # Analyze your codebase
    await orchestrator.analyze_project()

    # Execute tasks
    result = await orchestrator.run("Add user authentication")

    # Use specific agents
    result = await orchestrator.code("Implement login page")
    result = await orchestrator.api("Create REST endpoint for users")
    result = await orchestrator.scrape("Get headlines from bbc.com")

Sync Usage (for non-async code):
    from mcp_orchestrator import SyncOrchestrator

    orchestrator = SyncOrchestrator(project_path="./my-app")
    result = orchestrator.run("Add user login")
"""

from .orchestrator import Orchestrator, SyncOrchestrator
from .agents import Agent, AgentType
from .skills import Skill
from .hooks import Hook
from .setup import setup_project, list_available_agents, list_available_skills

__version__ = "0.1.0"
__all__ = [
    "Orchestrator",
    "SyncOrchestrator",
    "Agent",
    "AgentType",
    "Skill",
    "Hook",
    "setup_project",
    "list_available_agents",
    "list_available_skills",
]
