"""
Executor Agent

RESPONSIBILITY: Execute actions via skills.

This agent:
- Receives actions from the plan
- Executes them via skills
- Reports results
- NEVER decides if task is done
- NEVER decides if it should continue

The stop hook makes those decisions.
"""

from typing import Any, Dict, Optional
import asyncio

from .base_agent import BaseAgent, AgentContext, AgentResult


class ExecutorAgent(BaseAgent):
    """
    Executor Agent - Executes planned actions via skills.

    This agent is the workhorse that actually performs actions.
    It does NOT make decisions about continuation or termination.
    """

    def __init__(self):
        super().__init__(name="ExecutorAgent")
        self.skill_registry: Dict[str, Any] = {}

    def register_skill(self, name: str, skill: Any):
        """Register a skill that this executor can use."""
        self.skill_registry[name] = skill

    async def perform_step(self, context: AgentContext) -> AgentResult:
        """
        Execute a single action from the plan.
        """
        self.iteration_count += 1

        if not context.plan:
            return AgentResult(
                success=False,
                error="No plan provided to executor",
            )

        skill_name = context.plan.get("skill")
        args = context.plan.get("args", {})

        if not skill_name:
            return AgentResult(
                success=False,
                error="No skill specified in plan",
            )

        self.log("info", f"Executing skill: {skill_name}", {"args": args})

        try:
            result = await self._execute_skill(skill_name, args, context)
            return result
        except Exception as e:
            self.log("error", f"Skill execution failed: {str(e)}")
            return AgentResult(
                success=False,
                error=str(e),
                metadata={"skill": skill_name, "args": args},
            )

    async def _execute_skill(
        self,
        skill_name: str,
        args: Dict[str, Any],
        context: AgentContext
    ) -> AgentResult:
        """
        Execute a skill by name.
        """
        # Check if skill is registered
        if skill_name not in self.skill_registry:
            # Try to dynamically load the skill
            skill = await self._load_skill(skill_name)
            if not skill:
                return AgentResult(
                    success=False,
                    error=f"Skill not found: {skill_name}",
                )
            self.skill_registry[skill_name] = skill

        skill = self.skill_registry[skill_name]

        # Execute the skill
        try:
            if asyncio.iscoroutinefunction(skill.execute):
                result = await skill.execute(args, context)
            else:
                result = skill.execute(args, context)

            self.log("info", f"Skill {skill_name} completed", {
                "success": result.success,
                "has_data": result.data is not None,
            })

            return result

        except Exception as e:
            self.log("error", f"Skill {skill_name} raised exception", {
                "error": str(e),
            })
            return AgentResult(
                success=False,
                error=f"Skill execution error: {str(e)}",
            )

    async def _load_skill(self, skill_name: str) -> Optional[Any]:
        """
        Dynamically load a skill module.
        """
        try:
            # Import the skill module
            module = __import__(
                f"skills.{skill_name}",
                fromlist=[skill_name]
            )

            # Get the skill class (convention: SkillName from skill_name)
            class_name = "".join(word.capitalize() for word in skill_name.split("_"))
            skill_class = getattr(module, class_name, None)

            if skill_class:
                return skill_class()

            return None
        except ImportError as e:
            self.log("warning", f"Could not load skill: {skill_name}", {
                "error": str(e),
            })
            return None

    async def execute_multiple(
        self,
        steps: list,
        context: AgentContext
    ) -> list[AgentResult]:
        """
        Execute multiple steps in sequence.
        Stops on first failure unless continue_on_error is set.
        """
        results = []

        for step in steps:
            step_context = AgentContext(
                session_id=context.session_id,
                user_id=context.user_id,
                iteration=context.iteration,
                plan=step,
                previous_results=results.copy(),
                permissions=context.permissions,
                budget_remaining=context.budget_remaining,
                time_started=context.time_started,
            )

            result = await self.perform_step(step_context)
            results.append(result)

            # Stop on failure
            if not result.success:
                self.log("warning", "Stopping execution due to failure", {
                    "step": step.get("description", "unknown"),
                    "error": result.error,
                })
                break

        return results
