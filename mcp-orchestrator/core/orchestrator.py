"""
MCP Orchestrator - THE BRAIN

This is the central orchestration engine that:
- Receives user intent
- Creates plans via Planner Agent
- Spawns and coordinates subagents
- Runs hooks for safety and control
- Enforces the CORE EXECUTION LOOP

CANONICAL EXECUTION LOOP (from Part 2):

while True:
    agent.perform_step()
    write_logs()
    update_state()
    run_post_step_hooks()
    decision = run_stop_hook()

    if decision == CONTINUE:
        continue
    if decision == ESCALATE:
        pause_execution()
        wait_for_human()
        if human_approved:
            continue
        else:
            terminate()
    if decision == TERMINATE:
        finalize()
        break

ABSOLUTE RULE: Agents NEVER decide termination. ONLY the stop hook decides.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import asyncio

from ..agents import (
    AgentManager,
    AgentContext,
    AgentResult,
    AgentState,
)
from ..hooks import (
    StopHook,
    PreStepHook,
    PostStepHook,
    ApprovalHook,
    HookContext,
    HookAction,
)
from ..state import SessionStore, MemoryStore, AuditLogger, SessionState
from ..skills import CreateTaskLedger, VerifyTaskCompletion
from .config import Config


class MCPOrchestrator:
    """
    MCP Orchestrator - The brain of the autonomous system.

    This orchestrator:
    - Is the SINGLE entry point for execution
    - Coordinates all agents
    - Enforces all hooks
    - Controls the execution loop
    - Respects the task ledger as source of truth
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()

        # State management
        self.session_store = SessionStore(self.config.state.database_path)
        self.memory_store = MemoryStore(self.config.state.memory_database_path)
        self.audit_logger = AuditLogger(self.config.state.audit_log_path)

        # Agent management
        self.agent_manager = AgentManager(
            max_concurrent_agents=self.config.agents.max_concurrent_agents
        )

        # Hooks
        self.stop_hook = StopHook(
            max_iterations=self.config.safety.max_iterations,
            max_time_seconds=self.config.safety.max_time_seconds,
            max_budget=self.config.safety.max_budget_usd,
            max_retries=self.config.safety.max_retries_per_task,
        )
        self.pre_step_hook = PreStepHook()
        self.post_step_hook = PostStepHook()
        self.approval_hook = ApprovalHook(
            cost_threshold=self.config.safety.require_approval_above_cost,
            timeout_seconds=self.config.hooks.approval_hook_timeout_seconds,
        )

        # Skills
        self.create_task_ledger_skill = CreateTaskLedger()
        self.verify_completion_skill = VerifyTaskCompletion()

    async def execute(
        self,
        user_id: str,
        intent: str,
        budget_limit: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Execute the full autonomous workflow.

        This is the MAIN ENTRY POINT.

        Flow:
        1) Create session
        2) Create plan
        3) Create task ledger
        4) Execute loop until stop hook decides termination
        5) Return result
        """
        # Step 1: Create session
        session = self.session_store.create_session(
            user_id=user_id,
            intent=intent,
            budget_limit=budget_limit or self.config.safety.max_budget_usd,
        )

        self.audit_logger.log_session_start(session.session_id, user_id, intent)
        self.audit_logger.log_intent(session.session_id, user_id, intent)

        try:
            # Step 2: Create plan
            self.session_store.update_state(session.session_id, SessionState.PLANNING)
            plan = await self._create_plan(session, intent)

            if not plan:
                raise RuntimeError("Failed to create execution plan")

            session.plan = plan
            self.session_store.update_session(session.session_id, plan=plan)
            self.audit_logger.log_plan(session.session_id, user_id, plan)

            # Step 3: Create task ledger
            tasks = [step.get("description", f"Step {i+1}") for i, step in enumerate(plan.get("steps", []))]
            await self._create_task_ledger(session, tasks)

            # Step 4: Execute the autonomous loop
            self.session_store.update_state(session.session_id, SessionState.EXECUTING)
            result = await self._execution_loop(session)

            # Step 5: Finalize
            self.session_store.update_state(session.session_id, SessionState.COMPLETED)
            self.audit_logger.log_session_end(
                session.session_id,
                user_id,
                "completed",
                result
            )

            return {
                "success": True,
                "session_id": session.session_id,
                "result": result,
            }

        except Exception as e:
            self.session_store.update_state(session.session_id, SessionState.FAILED)
            self.audit_logger.log_error(
                session.session_id,
                user_id,
                "execution_error",
                str(e)
            )
            return {
                "success": False,
                "session_id": session.session_id,
                "error": str(e),
            }

    async def _create_plan(self, session, intent: str) -> Optional[Dict[str, Any]]:
        """Create execution plan via Planner Agent."""
        planner = self.agent_manager.get_or_spawn("planner")

        context = AgentContext(
            session_id=session.session_id,
            user_id=session.user_id,
            iteration=0,
            plan={"user_intent": intent, "action": "create_plan"},
            permissions=["plan:create"],
            budget_remaining=session.budget_limit,
            time_started=session.created_at,
        )

        result = await planner.perform_step(context)

        if result.success:
            return result.data
        return None

    async def _create_task_ledger(self, session, tasks: List[str]):
        """Create the task ledger for this session."""
        result = await self.create_task_ledger_skill.execute({
            "session_id": session.session_id,
            "tasks": tasks,
            "ledger_path": self.config.state.task_ledger_path,
            "json_path": self.config.state.tasks_json_path,
        })

        if not result.success:
            raise RuntimeError(f"Failed to create task ledger: {result.error}")

    async def _execution_loop(self, session) -> Dict[str, Any]:
        """
        THE CORE AUTONOMOUS EXECUTION LOOP.

        Per Part 2, this is THE HEART of the system.

        CANONICAL LOOP:
        while True:
            agent.perform_step()
            write_logs()
            update_state()
            run_post_step_hooks()
            decision = run_stop_hook()

            if decision == CONTINUE: continue
            if decision == ESCALATE: wait for human
            if decision == TERMINATE: break

        ABSOLUTE RULE: ONLY the stop hook decides termination.
        """
        results = []
        start_time = datetime.now()

        while True:
            # Get current iteration
            iteration = self.session_store.increment_iteration(session.session_id)

            # Get current session state
            session = self.session_store.get_session(session.session_id)

            # Create hook context
            hook_context = HookContext(
                session_id=session.session_id,
                agent_id="orchestrator",
                iteration=iteration,
                elapsed_time_seconds=(datetime.now() - start_time).total_seconds(),
                logs=session.logs[-50:],  # Last 50 logs
                budget_spent=session.budget_spent,
                budget_limit=session.budget_limit,
                task_ledger_path=self.config.state.tasks_json_path,
            )

            # Pre-step hook
            if self.config.hooks.pre_step_hook_enabled:
                pre_result = await self.pre_step_hook.execute(hook_context)
                if pre_result.action == HookAction.TERMINATE:
                    break
                if pre_result.action == HookAction.SKIP:
                    continue

            # Perform agent step
            step_result = await self._perform_step(session, iteration)
            results.append(step_result)

            # Write logs
            self.session_store.add_log(
                session.session_id,
                f"Iteration {iteration}: {step_result.get('action', 'unknown')}"
            )

            # Update state
            if step_result.get("cost", 0) > 0:
                self.session_store.add_cost(session.session_id, step_result["cost"])

            # Post-step hook
            if self.config.hooks.post_step_hook_enabled:
                post_result = await self.post_step_hook.execute(hook_context)
                hook_context.test_results = post_result.data

            # THE STOP HOOK - The most important decision
            if self.config.hooks.stop_hook_enabled:
                stop_decision = await self.stop_hook.execute(hook_context)

                self.audit_logger.log_hook_decision(
                    session.session_id,
                    session.user_id,
                    "stop_hook",
                    stop_decision.action.value,
                    stop_decision.reason,
                    stop_decision.confidence,
                )

                if stop_decision.action == HookAction.CONTINUE:
                    # Keep going
                    continue

                elif stop_decision.action == HookAction.ESCALATE:
                    # Pause and wait for human
                    self.session_store.update_state(
                        session.session_id,
                        SessionState.WAITING_APPROVAL
                    )

                    approval_result = await self.approval_hook.execute(hook_context)

                    if approval_result.action == HookAction.CONTINUE:
                        self.session_store.update_state(
                            session.session_id,
                            SessionState.EXECUTING
                        )
                        continue
                    else:
                        # Rejected or timeout
                        break

                elif stop_decision.action == HookAction.TERMINATE:
                    # Done!
                    break

        return {
            "iterations": iteration,
            "elapsed_seconds": (datetime.now() - start_time).total_seconds(),
            "budget_spent": session.budget_spent,
            "results_count": len(results),
            "final_result": results[-1] if results else None,
        }

    async def _perform_step(self, session, iteration: int) -> Dict[str, Any]:
        """
        Perform a single step of execution.

        Routes to the appropriate agent based on the plan.
        """
        plan = session.plan or {}
        steps = plan.get("steps", plan.get("plan", []))

        # Get current step (cycle through if we've done more iterations than steps)
        if not steps:
            return {"action": "no_steps", "success": False}

        step_index = (iteration - 1) % len(steps)
        current_step = steps[step_index]

        agent_type = current_step.get("agent", "executor")
        skill = current_step.get("skill", "")
        args = current_step.get("args", {})

        # Create context for this step
        context = AgentContext(
            session_id=session.session_id,
            user_id=session.user_id,
            iteration=iteration,
            plan=current_step,
            permissions=["execute:*"],
            budget_remaining=session.budget_limit - session.budget_spent,
            time_started=session.created_at,
        )

        # Route to agent
        result = await self.agent_manager.route_to_agent(agent_type, context)

        # Log the step
        self.audit_logger.log_agent_step(
            session.session_id,
            session.user_id,
            agent_type,
            iteration,
            skill or "step",
            result.to_dict() if hasattr(result, 'to_dict') else {},
            result.success,
            result.error,
        )

        return {
            "action": skill or current_step.get("description", "step"),
            "agent": agent_type,
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "cost": result.metadata.get("cost", 0) if result.metadata else 0,
        }

    async def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get the current status of a session."""
        session = self.session_store.get_session(session_id)
        if not session:
            return None

        # Check task completion
        completion = await self.verify_completion_skill.execute({
            "json_path": self.config.state.tasks_json_path,
        })

        return {
            "session_id": session_id,
            "state": session.state.value,
            "iteration": session.current_iteration,
            "budget_spent": session.budget_spent,
            "budget_limit": session.budget_limit,
            "task_completion": completion.data if completion.success else None,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
        }

    async def pause_session(self, session_id: str) -> bool:
        """Pause a running session."""
        session = self.session_store.get_session(session_id)
        if session and session.state == SessionState.EXECUTING:
            self.session_store.update_state(session_id, SessionState.PAUSED)
            return True
        return False

    async def resume_session(self, session_id: str) -> bool:
        """Resume a paused session."""
        session = self.session_store.get_session(session_id)
        if session and session.state == SessionState.PAUSED:
            self.session_store.update_state(session_id, SessionState.EXECUTING)
            return True
        return False

    async def terminate_session(self, session_id: str) -> bool:
        """Force terminate a session."""
        session = self.session_store.get_session(session_id)
        if session:
            self.session_store.update_state(session_id, SessionState.TERMINATED)
            self.audit_logger.log_session_end(
                session_id,
                session.user_id,
                "terminated",
                {"reason": "manual_termination"},
            )
            return True
        return False
