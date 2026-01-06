"""
Autonomous Operator

The main entry point for using the MCP Orchestrator as a library.

Usage:
    from mcp_orchestrator import AutonomousOperator

    operator = AutonomousOperator(project_path="/path/to/project")
    result = await operator.execute("Build a REST API for user management")

    if result.is_done:
        print("Task completed successfully!")
        print(result.summary)
    else:
        print(f"Task blocked: {result.blocked_reason}")
"""

import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ExecutionResult:
    """Result of executing a task."""
    task_id: str
    promise: str  # "<Promise>DONE</Promise>" or "<Promise>BLOCKED: reason</Promise>"
    status: str  # "done", "blocked", "error"
    steps_completed: int
    total_steps: int
    iterations_used: int
    results: List[Dict[str, Any]]
    started_at: str
    completed_at: str
    summary: str = ""
    blocked_reason: str = ""

    @property
    def is_done(self) -> bool:
        """Check if the task completed successfully."""
        return "DONE" in self.promise and "BLOCKED" not in self.promise

    @property
    def is_blocked(self) -> bool:
        """Check if the task is blocked."""
        return "BLOCKED" in self.promise

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "promise": self.promise,
            "status": self.status,
            "is_done": self.is_done,
            "is_blocked": self.is_blocked,
            "steps_completed": self.steps_completed,
            "total_steps": self.total_steps,
            "iterations_used": self.iterations_used,
            "results": self.results,
            "summary": self.summary,
            "blocked_reason": self.blocked_reason,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


class AutonomousOperator:
    """
    The Autonomous Operator - main interface for executing tasks.

    This class provides a clean API for using the MCP Orchestrator
    as a library in other projects.

    Features:
    - Execute any task by natural language description
    - Automatic routing to appropriate capabilities
    - Iterative execution with Ralph Wiggum pattern
    - Self-healing on errors
    - Dynamic capability creation
    - Comprehensive result reporting

    Example:
        operator = AutonomousOperator(project_path="/my/project")
        result = await operator.execute("Create a new user registration form")

        if result.is_done:
            print("Form created!")
        else:
            print(f"Could not complete: {result.blocked_reason}")
    """

    def __init__(
        self,
        project_path: str = None,
        max_iterations: int = 10,
        auto_create_capabilities: bool = True,
        run_tests: bool = True,
    ):
        """
        Initialize the Autonomous Operator.

        Args:
            project_path: Path to the project to operate on (defaults to cwd)
            max_iterations: Maximum retry iterations per step (default 10)
            auto_create_capabilities: Create new capabilities when needed
            run_tests: Run tests after task completion
        """
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self.max_iterations = max_iterations
        self.auto_create_capabilities = auto_create_capabilities
        self.run_tests = run_tests

        # Lazy-loaded components
        self._source_of_truth = None
        self._planning_agent = None
        self._execution_engine = None
        self._hook_system = None
        self._capability_creator = None

        # Callbacks for progress reporting
        self.on_step_start: Optional[Callable[[int, str], Awaitable[None]]] = None
        self.on_step_complete: Optional[Callable[[Dict], Awaitable[None]]] = None
        self.on_progress: Optional[Callable[[str], Awaitable[None]]] = None

    @property
    def source_of_truth(self):
        """Get the Source of Truth (lazy loaded)."""
        if self._source_of_truth is None:
            from .core.source_of_truth import get_source_of_truth
            self._source_of_truth = get_source_of_truth()
        return self._source_of_truth

    @property
    def planning_agent(self):
        """Get the Planning Agent (lazy loaded)."""
        if self._planning_agent is None:
            from .agents.planning_agent import get_planning_agent
            self._planning_agent = get_planning_agent()
        return self._planning_agent

    @property
    def execution_engine(self):
        """Get the Execution Engine (lazy loaded)."""
        if self._execution_engine is None:
            from .core.execution_engine import get_execution_engine
            self._execution_engine = get_execution_engine()
            self._execution_engine.max_iterations = self.max_iterations
            # Wire up callbacks
            if self.on_step_start:
                self._execution_engine.on_step_start = self.on_step_start
            if self.on_step_complete:
                self._execution_engine.on_step_complete = self.on_step_complete
        return self._execution_engine

    @property
    def hook_system(self):
        """Get the Hook System (lazy loaded)."""
        if self._hook_system is None:
            from .hooks.hook_system import get_hook_system
            self._hook_system = get_hook_system()
        return self._hook_system

    @property
    def capability_creator(self):
        """Get the Capability Creator (lazy loaded)."""
        if self._capability_creator is None:
            from .core.capability_creator import get_capability_creator
            self._capability_creator = get_capability_creator()
        return self._capability_creator

    async def execute(self, task_request: str, context: Dict[str, Any] = None) -> ExecutionResult:
        """
        Execute a task request.

        This is the main entry point for executing tasks. It:
        1. Analyzes the task request
        2. Creates an execution plan
        3. Routes to appropriate capabilities
        4. Executes with retry logic
        5. Runs tests if configured
        6. Returns comprehensive results

        Args:
            task_request: Natural language description of the task
            context: Optional context dictionary

        Returns:
            ExecutionResult with promise, status, and details
        """
        started_at = datetime.now().isoformat()

        try:
            # Report progress
            if self.on_progress:
                await self.on_progress(f"Analyzing task: {task_request}")

            # Step 1: Analyze and plan the task
            plan = await self.planning_agent.analyze_and_plan(task_request, context)

            if self.on_progress:
                await self.on_progress(f"Created plan with {len(plan.steps)} steps")

            # Step 2: Check if we need to create new capabilities
            if self.auto_create_capabilities and plan.clarifying_questions:
                # Check if any capability is missing
                for step in plan.steps:
                    if step.capability not in self.source_of_truth.capabilities:
                        if self.on_progress:
                            await self.on_progress(f"Creating new capability: {step.capability}")

                        result = await self.capability_creator.create_capability_for_task(
                            step.description
                        )
                        if result.get("needed"):
                            if self.on_progress:
                                await self.on_progress(f"Created: {result.get('capability')}")

            # Step 3: Execute the plan
            if self.on_progress:
                await self.on_progress("Starting execution...")

            from dataclasses import asdict
            plan_dict = {
                "task_id": plan.task_id,
                "steps": [asdict(step) for step in plan.steps],
                "max_iterations": self.max_iterations,
            }

            execution_result = await self.execution_engine.execute_plan(plan_dict)

            # Step 4: Run tests if configured
            tests_passed = True
            if self.run_tests:
                if self.on_progress:
                    await self.on_progress("Running tests...")

                from .hooks.hook_system import HookTrigger
                test_results = await self.hook_system.trigger(
                    HookTrigger.AFTER,
                    ["run-tests"],
                    {"project_path": str(self.project_path)}
                )
                tests_passed = all(r.success for r in test_results)

            # Step 5: Build the result
            completed_at = datetime.now().isoformat()

            # Determine final status
            is_done = execution_result.get("promise", "").find("DONE") != -1
            is_blocked = execution_result.get("promise", "").find("BLOCKED") != -1

            blocked_reason = ""
            if is_blocked:
                # Extract reason from promise
                promise = execution_result.get("promise", "")
                if "BLOCKED:" in promise:
                    blocked_reason = promise.split("BLOCKED:")[1].split("</Promise>")[0].strip()

            # Generate summary
            summary = self._generate_summary(plan, execution_result, tests_passed)

            return ExecutionResult(
                task_id=plan.task_id,
                promise=execution_result.get("promise", "<Promise>DONE</Promise>"),
                status="done" if is_done else "blocked" if is_blocked else "error",
                steps_completed=execution_result.get("steps_completed", 0),
                total_steps=execution_result.get("total_steps", len(plan.steps)),
                iterations_used=execution_result.get("iterations_used", 0),
                results=execution_result.get("results", []),
                started_at=started_at,
                completed_at=completed_at,
                summary=summary,
                blocked_reason=blocked_reason,
            )

        except Exception as e:
            return ExecutionResult(
                task_id=f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                promise=f"<Promise>BLOCKED: {str(e)}</Promise>",
                status="error",
                steps_completed=0,
                total_steps=0,
                iterations_used=0,
                results=[],
                started_at=started_at,
                completed_at=datetime.now().isoformat(),
                summary=f"Error executing task: {str(e)}",
                blocked_reason=str(e),
            )

    def _generate_summary(self, plan, execution_result: Dict, tests_passed: bool) -> str:
        """Generate a human-readable summary of the execution."""
        lines = [
            f"Task: {plan.understood_goal}",
            f"Category: {plan.category}",
            f"Complexity: {plan.estimated_complexity}",
            f"Steps completed: {execution_result.get('steps_completed', 0)}/{len(plan.steps)}",
            f"Iterations used: {execution_result.get('iterations_used', 0)}",
            f"Tests passed: {'Yes' if tests_passed else 'No'}",
        ]

        promise = execution_result.get("promise", "")
        if "DONE" in promise:
            lines.append("Status: COMPLETED SUCCESSFULLY")
        elif "BLOCKED" in promise:
            lines.append("Status: BLOCKED")

        return "\n".join(lines)

    async def fix_issue(self, issue: str, error_logs: str = None, affected_file: str = None) -> Dict[str, Any]:
        """
        Self-heal by fixing an issue.

        Args:
            issue: Description of the issue
            error_logs: Optional error logs
            affected_file: Optional path to affected file

        Returns:
            Result dictionary with success status
        """
        from .core.self_healing import get_self_healer
        healer = get_self_healer()
        return await healer.analyze_and_fix(issue, error_logs, affected_file)

    async def create_capability(self, task_description: str) -> Dict[str, Any]:
        """
        Create a new capability for handling a specific type of task.

        Args:
            task_description: Description of what the capability should do

        Returns:
            Result dictionary with created capability info
        """
        return await self.capability_creator.analyze_and_create(task_description)

    def get_capabilities(self) -> Dict[str, Any]:
        """Get all registered capabilities."""
        return {
            name: {
                "type": cap.type.value,
                "description": cap.description,
                "triggers": cap.triggers,
            }
            for name, cap in self.source_of_truth.capabilities.items()
        }

    async def route_task(self, task_description: str) -> Dict[str, Any]:
        """
        Route a task to appropriate capabilities without executing.

        Useful for previewing what would happen for a task.

        Args:
            task_description: The task to route

        Returns:
            Routing information including primary capability and hooks
        """
        return self.source_of_truth.route_task(task_description)


# Convenience function for quick execution
async def execute_task(
    task_request: str,
    project_path: str = None,
    max_iterations: int = 10,
) -> ExecutionResult:
    """
    Quick convenience function to execute a task.

    Example:
        from mcp_orchestrator import execute_task

        result = await execute_task("Create a login form")
        print(result.promise)
    """
    operator = AutonomousOperator(
        project_path=project_path,
        max_iterations=max_iterations,
    )
    return await operator.execute(task_request)
