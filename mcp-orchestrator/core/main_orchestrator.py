"""
Main Orchestrator - The Central Nervous System

This is the MAIN entry point that connects ALL components:
1. Source of Truth - routes tasks to capabilities
2. Planning Agent - creates execution plans
3. Execution Engine - runs with Ralph Wiggum retries
4. Hook System - fires before/after hooks
5. TODO.md - tracks all tasks with promises
6. Capability Creator - creates new capabilities when needed

EVERY task MUST go through this orchestrator.
NO task is complete without <Promise>DONE</Promise>.
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class OrchestrationResult:
    """Result of orchestrating a task."""
    task_id: str
    promise: str  # <Promise>DONE</Promise> or <Promise>BLOCKED: reason</Promise>
    status: str  # done, blocked, error, in_progress
    message: str
    plan: Optional[Dict] = None
    execution: Optional[Dict] = None
    results: Optional[List[Dict]] = None
    hooks_fired: Optional[List[str]] = None
    todo_updated: bool = False


class MainOrchestrator:
    """
    The Main Orchestrator - connects all system components.

    This is THE entry point for ALL tasks. Nothing bypasses this.

    Flow:
    1. Task Request → Source of Truth (routing)
    2. → Planning Agent (create plan)
    3. → Hook System (BEFORE hooks)
    4. → Execution Engine (run with retries)
    5. → Hook System (AFTER hooks)
    6. → TODO.md (update status)
    7. → <Promise>DONE</Promise> or <Promise>BLOCKED</Promise>
    """

    def __init__(self):
        self.base_path = Path(__file__).parent.parent

        # Lazy-loaded components
        self._source_of_truth = None
        self._planning_agent = None
        self._execution_engine = None
        self._hook_system = None
        self._capability_creator = None

        # Task tracking
        self.active_tasks: Dict[str, Dict] = {}

        # Callbacks
        self.on_task_start: Optional[Callable[[str, str], Awaitable[None]]] = None
        self.on_task_progress: Optional[Callable[[str, str], Awaitable[None]]] = None
        self.on_task_complete: Optional[Callable[[OrchestrationResult], Awaitable[None]]] = None

    @property
    def source_of_truth(self):
        """Get Source of Truth (lazy loaded)."""
        if self._source_of_truth is None:
            from core.source_of_truth import get_source_of_truth
            self._source_of_truth = get_source_of_truth()
        return self._source_of_truth

    @property
    def planning_agent(self):
        """Get Planning Agent (lazy loaded)."""
        if self._planning_agent is None:
            from agents.planning_agent import get_planning_agent
            self._planning_agent = get_planning_agent()
        return self._planning_agent

    @property
    def execution_engine(self):
        """Get Execution Engine (lazy loaded)."""
        if self._execution_engine is None:
            from core.execution_engine import get_execution_engine
            self._execution_engine = get_execution_engine()
        return self._execution_engine

    @property
    def hook_system(self):
        """Get Hook System (lazy loaded)."""
        if self._hook_system is None:
            from hooks.hook_system import get_hook_system
            self._hook_system = get_hook_system()
        return self._hook_system

    @property
    def capability_creator(self):
        """Get Capability Creator (lazy loaded)."""
        if self._capability_creator is None:
            from core.capability_creator import get_capability_creator
            self._capability_creator = get_capability_creator()
        return self._capability_creator

    async def orchestrate(self, task_request: str, context: Dict = None) -> OrchestrationResult:
        """
        Main orchestration entry point.

        This method:
        1. Consults Source of Truth for routing
        2. Creates an execution plan
        3. Fires BEFORE hooks
        4. Executes with retry logic
        5. Fires AFTER hooks
        6. Updates TODO.md
        7. Returns result with Promise

        Args:
            task_request: Natural language task description
            context: Optional context dictionary

        Returns:
            OrchestrationResult with promise status
        """
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        hooks_fired = []

        # Track active task
        self.active_tasks[task_id] = {
            "request": task_request,
            "status": "starting",
            "started_at": datetime.now().isoformat(),
        }

        try:
            # Notify start
            if self.on_task_start:
                await self.on_task_start(task_id, task_request)

            # ========================================
            # STEP 1: Consult Source of Truth
            # ========================================
            await self._progress(task_id, "Consulting Source of Truth for routing...")
            routing = self.source_of_truth.route_task(task_request)

            self.active_tasks[task_id]["routing"] = routing

            # ========================================
            # STEP 2: Create Execution Plan
            # ========================================
            await self._progress(task_id, "Creating execution plan...")
            plan = await self.planning_agent.analyze_and_plan(task_request, context)

            self.active_tasks[task_id]["plan"] = asdict(plan)
            self.active_tasks[task_id]["status"] = "planned"

            # ========================================
            # STEP 3: Fire BEFORE hooks
            # ========================================
            await self._progress(task_id, "Running BEFORE hooks...")
            before_hooks = routing.get("hooks_before", []) + ["check-design-patterns", "load-design-system"]

            from hooks.hook_system import HookTrigger
            before_results = await self.hook_system.trigger(
                HookTrigger.BEFORE,
                before_hooks,
                {
                    "task_id": task_id,
                    "task_request": task_request,
                    "routing": routing,
                    "plan": asdict(plan),
                }
            )

            for hr in before_results:
                hooks_fired.append(f"BEFORE:{hr.hook_name}")
                if not hr.success:
                    # BEFORE hook blocked execution
                    return OrchestrationResult(
                        task_id=task_id,
                        promise=f"<Promise>BLOCKED: {hr.hook_name} blocked - {hr.error}</Promise>",
                        status="blocked",
                        message=f"Hook {hr.hook_name} blocked execution",
                        hooks_fired=hooks_fired,
                    )

            # ========================================
            # STEP 4: Execute Plan with Retries
            # ========================================
            await self._progress(task_id, "Executing plan (Ralph Wiggum pattern)...")
            self.active_tasks[task_id]["status"] = "executing"

            plan_dict = {
                "task_id": task_id,
                "steps": [asdict(step) for step in plan.steps],
                "max_iterations": 10,
            }

            execution_result = await self.execution_engine.execute_plan(plan_dict)

            self.active_tasks[task_id]["execution"] = execution_result

            # ========================================
            # STEP 5: Fire AFTER hooks
            # ========================================
            await self._progress(task_id, "Running AFTER hooks...")
            after_hooks = routing.get("hooks_after", []) + ["update-todo", "run-tests"]

            after_results = await self.hook_system.trigger(
                HookTrigger.AFTER,
                after_hooks,
                {
                    "task_id": task_id,
                    "task_request": task_request,
                    "execution_result": execution_result,
                    "status": "done" if "DONE" in execution_result.get("promise", "") else "blocked",
                }
            )

            for hr in after_results:
                hooks_fired.append(f"AFTER:{hr.hook_name}")

            # ========================================
            # STEP 6: Update TODO.md
            # ========================================
            await self._progress(task_id, "Updating TODO.md...")
            todo_updated = await self._update_todo(task_id, plan, execution_result)

            # ========================================
            # STEP 7: Fire ON_COMPLETE hook
            # ========================================
            is_done = "DONE" in execution_result.get("promise", "")
            tests_passed = any("run-tests" in h and "AFTER" in h for h in hooks_fired)

            completion_result = await self.hook_system.trigger_on_complete({
                "task_id": task_id,
                "all_steps_done": is_done,
                "tests_passed": tests_passed,
            })
            hooks_fired.append(f"ON_COMPLETE:{completion_result.hook_name}")

            # ========================================
            # STEP 8: Return Result with Promise
            # ========================================
            self.active_tasks[task_id]["status"] = "done" if is_done else "blocked"
            self.active_tasks[task_id]["completed_at"] = datetime.now().isoformat()

            result = OrchestrationResult(
                task_id=task_id,
                promise=execution_result.get("promise", "<Promise>BLOCKED: Unknown</Promise>"),
                status="done" if is_done else "blocked",
                message=f"Task {'completed' if is_done else 'blocked'}",
                plan=asdict(plan),
                execution=execution_result,
                results=execution_result.get("results", []),
                hooks_fired=hooks_fired,
                todo_updated=todo_updated,
            )

            if self.on_task_complete:
                await self.on_task_complete(result)

            return result

        except Exception as e:
            self.active_tasks[task_id]["status"] = "error"
            self.active_tasks[task_id]["error"] = str(e)

            return OrchestrationResult(
                task_id=task_id,
                promise=f"<Promise>BLOCKED: {str(e)}</Promise>",
                status="error",
                message=str(e),
                hooks_fired=hooks_fired,
            )

    async def _progress(self, task_id: str, message: str):
        """Report progress."""
        self.active_tasks[task_id]["last_progress"] = message
        if self.on_task_progress:
            await self.on_task_progress(task_id, message)

    async def _update_todo(self, task_id: str, plan, execution_result: Dict) -> bool:
        """Update TODO.md with task status."""
        try:
            todo_path = self.base_path / "TODO.md"
            if not todo_path.exists():
                return False

            content = todo_path.read_text()

            # Add task entry if not exists
            if task_id not in content:
                is_done = "DONE" in execution_result.get("promise", "")
                status = "DONE" if is_done else "BLOCKED"
                promise = execution_result.get("promise", "<Promise>PENDING</Promise>")

                new_task = f"""

## Task: {task_id}

**Request:** {plan.original_request}
**Goal:** {plan.understood_goal}
**Category:** {plan.category}
**Complexity:** {plan.estimated_complexity}
**Created:** {plan.created_at}

### Steps:
"""
                for step in plan.steps:
                    marker = "[x]" if is_done else "[!]"
                    new_task += f"{step.number}. {marker} {step.description}\n"
                    new_task += f"   - Capability: `{step.capability}` ({step.capability_type})\n"

                new_task += f"""
### Status: {status}

### Completion:
```
{promise}
```

---
"""
                # Insert after "## Active Tasks"
                if "## Active Tasks" in content:
                    content = content.replace(
                        "## Active Tasks\n",
                        f"## Active Tasks\n{new_task}"
                    )
                else:
                    content += new_task

                todo_path.write_text(content)

            return True

        except Exception as e:
            print(f"Failed to update TODO.md: {e}")
            return False

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        if task_id in self.active_tasks:
            self.active_tasks[task_id]["status"] = "cancelled"
            return True
        return False

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Get status of a task."""
        return self.active_tasks.get(task_id)

    def get_all_tasks(self) -> Dict[str, Dict]:
        """Get all tracked tasks."""
        return self.active_tasks


# Singleton
_orchestrator: Optional[MainOrchestrator] = None


def get_main_orchestrator() -> MainOrchestrator:
    """Get the singleton Main Orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = MainOrchestrator()
    return _orchestrator


async def orchestrate_task(task_request: str, context: Dict = None) -> OrchestrationResult:
    """Convenience function to orchestrate a task."""
    orchestrator = get_main_orchestrator()
    return await orchestrator.orchestrate(task_request, context)
