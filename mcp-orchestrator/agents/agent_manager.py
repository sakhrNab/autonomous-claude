"""
Agent Manager

RESPONSIBILITY: Spawn and coordinate all subagents.

This is the central coordinator that:
- Creates agent instances
- Routes tasks to correct agents
- Manages agent lifecycle
- Coordinates inter-agent communication
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Type
import asyncio

from .base_agent import BaseAgent, AgentContext, AgentResult, AgentState
from .planner_agent import PlannerAgent
from .executor_agent import ExecutorAgent
from .monitor_agent import MonitorAgent
from .debugger_agent import DebuggerAgent
from .approval_agent import ApprovalAgent
from .task_manager_agent import TaskManagerAgent


class AgentManager:
    """
    Agent Manager - The coordinator for all subagents.

    This manager:
    - Maintains the agent registry
    - Spawns agents as needed
    - Routes actions to appropriate agents
    - Handles inter-agent communication
    - Manages agent lifecycle
    """

    def __init__(self, max_concurrent_agents: int = 10):
        self.max_concurrent_agents = max_concurrent_agents
        self.agents: Dict[str, BaseAgent] = {}
        self.agent_types: Dict[str, Type[BaseAgent]] = {
            "planner": PlannerAgent,
            "executor": ExecutorAgent,
            "monitor": MonitorAgent,
            "debugger": DebuggerAgent,
            "approval": ApprovalAgent,
            "task_manager": TaskManagerAgent,
        }
        self.created_at = datetime.now()

    def spawn_agent(self, agent_type: str, **kwargs) -> BaseAgent:
        """
        Spawn a new agent of the specified type.
        """
        if agent_type not in self.agent_types:
            raise ValueError(f"Unknown agent type: {agent_type}")

        if len(self.agents) >= self.max_concurrent_agents:
            raise RuntimeError("Maximum concurrent agents reached")

        agent_class = self.agent_types[agent_type]
        agent = agent_class(**kwargs)
        self.agents[agent.agent_id] = agent

        return agent

    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """Get an agent by ID."""
        return self.agents.get(agent_id)

    def get_agent_by_type(self, agent_type: str) -> Optional[BaseAgent]:
        """Get the first agent of a specific type."""
        for agent in self.agents.values():
            if agent.name.lower().replace("agent", "") == agent_type.lower():
                return agent
        return None

    def get_or_spawn(self, agent_type: str, **kwargs) -> BaseAgent:
        """Get an existing agent of a type or spawn a new one."""
        existing = self.get_agent_by_type(agent_type)
        if existing:
            return existing
        return self.spawn_agent(agent_type, **kwargs)

    async def route_to_agent(
        self,
        agent_type: str,
        context: AgentContext
    ) -> AgentResult:
        """
        Route a task to the appropriate agent.
        """
        agent = self.get_or_spawn(agent_type)

        # Initialize if needed
        if agent.state == AgentState.IDLE:
            await agent.initialize(context)

        # Perform the step
        result = await agent.perform_step(context)

        return result

    async def execute_plan(
        self,
        plan: List[Dict[str, Any]],
        base_context: AgentContext
    ) -> List[AgentResult]:
        """
        Execute a full plan by routing steps to appropriate agents.
        """
        results = []

        for i, step in enumerate(plan):
            agent_type = step.get("agent", "executor")

            # Create context for this step
            step_context = AgentContext(
                session_id=base_context.session_id,
                user_id=base_context.user_id,
                iteration=i + 1,
                plan=step,
                previous_results=results.copy(),
                permissions=base_context.permissions,
                budget_remaining=base_context.budget_remaining,
                time_started=base_context.time_started,
            )

            result = await self.route_to_agent(agent_type, step_context)
            results.append(result)

            # Stop on critical failure
            if not result.success and step.get("critical", False):
                break

        return results

    def terminate_agent(self, agent_id: str):
        """Terminate and remove an agent."""
        if agent_id in self.agents:
            agent = self.agents.pop(agent_id)
            agent.state = AgentState.COMPLETED

    async def cleanup_all(self):
        """Clean up all agents."""
        for agent in self.agents.values():
            await agent.cleanup()
        self.agents.clear()

    def get_all_logs(self) -> List[Dict[str, Any]]:
        """Get logs from all agents."""
        all_logs = []
        for agent in self.agents.values():
            all_logs.extend(agent.get_logs())
        return sorted(all_logs, key=lambda x: x["timestamp"])

    def get_status(self) -> Dict[str, Any]:
        """Get status of all agents."""
        return {
            "total_agents": len(self.agents),
            "max_agents": self.max_concurrent_agents,
            "agents": [
                {
                    "agent_id": agent.agent_id,
                    "name": agent.name,
                    "state": agent.state.value,
                    "iterations": agent.iteration_count,
                }
                for agent in self.agents.values()
            ],
        }

    def register_agent_type(self, name: str, agent_class: Type[BaseAgent]):
        """Register a new agent type."""
        self.agent_types[name] = agent_class
