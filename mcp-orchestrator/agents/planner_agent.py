"""
Planner Agent

RESPONSIBILITY: Turn user intent into an executable plan.

Inputs:
- User message (voice -> text)
- Session context
- User permissions

Outputs:
- Ordered list of steps with agent, skill, and arguments
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import json

from .base_agent import BaseAgent, AgentContext, AgentResult


@dataclass
class PlanStep:
    """A single step in an execution plan."""
    step_number: int
    agent: str
    skill: str
    args: Dict[str, Any]
    description: str
    requires_approval: bool = False
    estimated_cost: float = 0.0


class PlannerAgent(BaseAgent):
    """
    Planner Agent - Converts user intent to execution plans.

    This agent:
    - Analyzes user intent
    - Creates ordered step lists
    - Identifies required skills
    - Determines which agents handle each step
    - Expands tasks if complexity increases
    """

    def __init__(self):
        super().__init__(name="PlannerAgent")
        self.current_plan: List[PlanStep] = []

    async def perform_step(self, context: AgentContext) -> AgentResult:
        """
        Create or refine an execution plan based on user intent.
        """
        self.iteration_count += 1

        user_intent = context.plan.get("user_intent", "") if context.plan else ""
        action = context.plan.get("action", "create_plan") if context.plan else "create_plan"

        if action == "create_plan":
            return await self._create_plan(user_intent, context)
        elif action == "expand_task":
            return await self._expand_task(context)
        elif action == "get_current_plan":
            return self._get_current_plan()
        else:
            return AgentResult(
                success=False,
                error=f"Unknown action: {action}",
            )

    async def _create_plan(self, user_intent: str, context: AgentContext) -> AgentResult:
        """
        Create an execution plan from user intent.

        This is where the planner analyzes what the user wants
        and creates a series of steps to achieve it.
        """
        self.log("info", "Creating plan", {"intent": user_intent})

        # Analyze intent and create plan
        steps = self._analyze_intent(user_intent, context)

        if not steps:
            return AgentResult(
                success=False,
                error="Could not create plan from intent",
            )

        self.current_plan = steps

        # Create initial tasks for task ledger
        tasks = [step.description for step in steps]

        self.log("info", "Plan created", {"step_count": len(steps)})

        return AgentResult(
            success=True,
            data={
                "plan": [self._step_to_dict(s) for s in steps],
                "tasks_to_create": tasks,
                "total_steps": len(steps),
                "requires_approval": any(s.requires_approval for s in steps),
                "estimated_total_cost": sum(s.estimated_cost for s in steps),
            },
        )

    def _analyze_intent(self, intent: str, context: AgentContext) -> List[PlanStep]:
        """
        Analyze user intent and generate plan steps.

        This is a simplified implementation. In production,
        this would use an LLM or more sophisticated NLP.
        """
        steps = []
        intent_lower = intent.lower()

        # Pattern matching for common intents
        if "pipeline" in intent_lower or "deploy" in intent_lower:
            steps.append(PlanStep(
                step_number=1,
                agent="executor",
                skill="run_pipeline",
                args={"pipeline_name": self._extract_pipeline_name(intent)},
                description="Run deployment pipeline",
            ))
            steps.append(PlanStep(
                step_number=2,
                agent="monitor",
                skill="query_status",
                args={"job_type": "pipeline"},
                description="Monitor pipeline status",
            ))

        if "workflow" in intent_lower:
            steps.append(PlanStep(
                step_number=1,
                agent="executor",
                skill="run_workflow",
                args={"workflow_name": self._extract_workflow_name(intent)},
                description="Execute workflow",
            ))

        if "fix" in intent_lower or "debug" in intent_lower:
            steps.append(PlanStep(
                step_number=1,
                agent="debugger",
                skill="fetch_logs",
                args={},
                description="Fetch error logs",
            ))
            steps.append(PlanStep(
                step_number=2,
                agent="debugger",
                skill="apply_fix",
                args={"auto_retry": True},
                description="Apply fix and retry",
                requires_approval=True,
            ))

        if "test" in intent_lower:
            steps.append(PlanStep(
                step_number=len(steps) + 1,
                agent="executor",
                skill="run_pipeline",
                args={"pipeline_name": "test", "type": "test"},
                description="Run tests",
            ))

        if "notify" in intent_lower or "alert" in intent_lower:
            steps.append(PlanStep(
                step_number=len(steps) + 1,
                agent="executor",
                skill="send_notification",
                args={"channel": "default"},
                description="Send notification",
            ))

        # Default: if no specific intent matched, create a general plan
        if not steps:
            steps.append(PlanStep(
                step_number=1,
                agent="executor",
                skill="run_workflow",
                args={"intent": intent},
                description=f"Execute: {intent}",
            ))

        # Add monitoring step at the end
        if steps and steps[-1].agent != "monitor":
            steps.append(PlanStep(
                step_number=len(steps) + 1,
                agent="monitor",
                skill="query_status",
                args={},
                description="Verify completion",
            ))

        return steps

    def _extract_pipeline_name(self, intent: str) -> str:
        """Extract pipeline name from intent."""
        # Simple extraction - would be more sophisticated in production
        words = intent.split()
        for i, word in enumerate(words):
            if word.lower() == "pipeline" and i + 1 < len(words):
                return words[i + 1]
        return "default"

    def _extract_workflow_name(self, intent: str) -> str:
        """Extract workflow name from intent."""
        words = intent.split()
        for i, word in enumerate(words):
            if word.lower() == "workflow" and i + 1 < len(words):
                return words[i + 1]
        return "default"

    async def _expand_task(self, context: AgentContext) -> AgentResult:
        """
        Expand a task into subtasks if complexity increases.
        """
        task_id = context.plan.get("task_id") if context.plan else None

        if not task_id:
            return AgentResult(
                success=False,
                error="No task_id provided for expansion",
            )

        # Find the task in current plan and expand it
        new_steps = []
        for step in self.current_plan:
            if step.description == task_id:
                # Expand this step into multiple
                expanded = self._expand_step(step)
                new_steps.extend(expanded)
            else:
                new_steps.append(step)

        # Renumber steps
        for i, step in enumerate(new_steps):
            step.step_number = i + 1

        self.current_plan = new_steps

        return AgentResult(
            success=True,
            data={
                "expanded_plan": [self._step_to_dict(s) for s in new_steps],
                "new_tasks": [s.description for s in new_steps if s.description != task_id],
            },
        )

    def _expand_step(self, step: PlanStep) -> List[PlanStep]:
        """Expand a complex step into multiple smaller steps."""
        # This would be more sophisticated in production
        return [step]  # Default: no expansion

    def _get_current_plan(self) -> AgentResult:
        """Return the current plan."""
        return AgentResult(
            success=True,
            data={
                "plan": [self._step_to_dict(s) for s in self.current_plan],
                "total_steps": len(self.current_plan),
            },
        )

    def _step_to_dict(self, step: PlanStep) -> Dict[str, Any]:
        """Convert a PlanStep to dictionary."""
        return {
            "step_number": step.step_number,
            "agent": step.agent,
            "skill": step.skill,
            "args": step.args,
            "description": step.description,
            "requires_approval": step.requires_approval,
            "estimated_cost": step.estimated_cost,
        }
