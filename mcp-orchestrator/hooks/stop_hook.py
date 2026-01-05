"""
Stop Hook - THE MOST IMPORTANT HOOK

The Stop Hook decides:
- continue
- terminate
- escalate

It runs AFTER EACH AGENT ITERATION.

ABSOLUTE RULE: Agents NEVER decide termination. ONLY the stop hook decides.

Per the Master Guide:
- IF any task != Completed: action = CONTINUE
- ONLY WHEN all tasks == Completed AND final verification passes:
  -> TERMINATE IS ALLOWED
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import json

from .base_hook import BaseHook, HookContext, HookResult, HookAction


class StopHook(BaseHook):
    """
    Stop Hook - The gatekeeper of execution termination.

    This is what enables:
    "CONTINUE CODING UNTIL IT IS ACTUALLY DONE"

    Decision Tree (ORDER OF EVALUATION):

    1) HARD STOPS (NO EXCEPTIONS)
       - iteration_count > MAX_ITERS -> TERMINATE
       - elapsed_time > MAX_TIME -> TERMINATE
       - budget_exceeded -> TERMINATE
       - permission_violation -> TERMINATE

    2) TASK LEDGER CHECK (MASTER GUIDE RULE)
       - any task != Completed -> CONTINUE
       - reason = "tasks_remaining"

    2.5) MESSAGE-LINKED TASK CHECK (SESSION 2 RULE)
       - any message has incomplete linked tasks -> CONTINUE
       - Stop Hook cannot terminate until linked tasks complete

    3) SUCCESS TESTS
       - all tests pass -> TERMINATE (SUCCESS)

    4) KNOWN FAILURE WITH REMEDIATION
       - error matches known pattern
       - remediation exists
       - retry count < MAX_RETRIES
       -> CONTINUE

    5) UNKNOWN / RISKY FAILURE
       - destructive action
       - high cost
       - unclear impact
       -> ESCALATE

    6) DEFAULT -> CONTINUE
    """

    name = "StopHook"
    description = "Determines whether to continue, terminate, or escalate execution"

    def __init__(
        self,
        max_iterations: int = 100,
        max_time_seconds: int = 3600,
        max_budget: float = 100.0,
        max_retries: int = 5,
        message_store=None
    ):
        super().__init__()
        self.max_iterations = max_iterations
        self.max_time_seconds = max_time_seconds
        self.max_budget = max_budget
        self.max_retries = max_retries
        self.retry_counts: Dict[str, int] = {}
        self.message_store = message_store  # SESSION 2: For message-linked task enforcement

    async def execute(self, context: HookContext) -> HookResult:
        """
        Execute the stop hook decision tree.

        This method MUST be called after every agent iteration.
        """
        # Step 1: HARD STOPS
        hard_stop = self._check_hard_stops(context)
        if hard_stop:
            self.record_result(hard_stop)
            return hard_stop

        # Step 2: TASK LEDGER CHECK (Critical per Master Guide)
        task_check = await self._check_task_ledger(context)
        if task_check.action == HookAction.CONTINUE:
            self.record_result(task_check)
            return task_check

        # Step 2.5: MESSAGE-LINKED TASK CHECK (SESSION 2 Rule)
        message_check = await self._check_message_linked_tasks(context)
        if message_check.action == HookAction.CONTINUE:
            self.record_result(message_check)
            return message_check

        # Step 3: SUCCESS TESTS
        if context.test_results:
            test_check = self._check_tests(context.test_results)
            if test_check.action == HookAction.TERMINATE:
                self.record_result(test_check)
                return test_check

        # Step 4: KNOWN FAILURE WITH REMEDIATION
        remediation = self._check_remediation(context)
        if remediation:
            self.record_result(remediation)
            return remediation

        # Step 5: UNKNOWN / RISKY FAILURE
        escalation = self._check_escalation(context)
        if escalation:
            self.record_result(escalation)
            return escalation

        # Step 6: DEFAULT - CONTINUE
        default_result = HookResult(
            action=HookAction.CONTINUE,
            reason="default_continue",
            confidence=0.7,
            next_expected_state="execution_continues",
        )
        self.record_result(default_result)
        return default_result

    def _check_hard_stops(self, context: HookContext) -> Optional[HookResult]:
        """
        Check hard stop conditions.
        These are NON-NEGOTIABLE and trigger immediate termination.
        """
        # Max iterations
        if context.iteration >= self.max_iterations:
            return HookResult(
                action=HookAction.TERMINATE,
                reason="max_iterations_exceeded",
                confidence=1.0,
                data={
                    "iteration": context.iteration,
                    "max_iterations": self.max_iterations,
                },
            )

        # Max time
        if context.elapsed_time_seconds >= self.max_time_seconds:
            return HookResult(
                action=HookAction.TERMINATE,
                reason="max_time_exceeded",
                confidence=1.0,
                data={
                    "elapsed": context.elapsed_time_seconds,
                    "max_time": self.max_time_seconds,
                },
            )

        # Budget exceeded
        if context.budget_spent >= context.budget_limit:
            return HookResult(
                action=HookAction.TERMINATE,
                reason="budget_exceeded",
                confidence=1.0,
                data={
                    "spent": context.budget_spent,
                    "limit": context.budget_limit,
                },
            )

        return None

    async def _check_task_ledger(self, context: HookContext) -> HookResult:
        """
        Check the task ledger for completion.

        Per the Master Guide:
        IF any task != Completed:
            action = CONTINUE
            reason = "tasks_remaining"

        ONLY WHEN all tasks == Completed:
            TERMINATE IS ALLOWED
        """
        try:
            ledger_path = Path(context.task_ledger_path)

            if not ledger_path.exists():
                # No ledger = execution forbidden, but continue to create one
                return HookResult(
                    action=HookAction.CONTINUE,
                    reason="no_task_ledger",
                    confidence=1.0,
                    data={"message": "Task ledger not found, continuing to create"},
                )

            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            tasks = ledger.get("tasks", [])

            incomplete = []
            blocked = []

            for task in tasks:
                state = task.get("state", "pending")
                if state == "blocked":
                    blocked.append(task["id"])
                elif state != "completed":
                    incomplete.append(task["id"])

            # If any tasks are not complete, CONTINUE
            if incomplete or blocked:
                return HookResult(
                    action=HookAction.CONTINUE,
                    reason="tasks_remaining",
                    confidence=1.0,
                    data={
                        "incomplete_count": len(incomplete),
                        "blocked_count": len(blocked),
                        "incomplete_tasks": incomplete,
                        "blocked_tasks": blocked,
                    },
                    next_expected_state="tasks_complete",
                )

            # All tasks complete - termination is allowed
            return HookResult(
                action=HookAction.TERMINATE,
                reason="all_tasks_complete",
                confidence=1.0,
                data={"total_tasks": len(tasks)},
            )

        except Exception as e:
            # Error reading ledger - continue but log
            return HookResult(
                action=HookAction.CONTINUE,
                reason="task_ledger_error",
                confidence=0.5,
                data={"error": str(e)},
            )

    async def _check_message_linked_tasks(self, context: HookContext) -> HookResult:
        """
        Check that all message-linked tasks are complete.

        Per SESSION 2 Guide:
        - All messages generate linked tasks
        - Stop Hook cannot terminate until linked tasks complete
        """
        if not self.message_store:
            # No message store - skip this check
            return HookResult(
                action=HookAction.TERMINATE,
                reason="no_message_store",
                confidence=0.8,
                data={"message": "Message store not configured, skipping check"},
            )

        try:
            # Get messages with incomplete linked tasks
            incomplete_messages = self.message_store.get_messages_with_incomplete_tasks()

            if incomplete_messages:
                # Get task ledger to cross-reference
                ledger_path = Path(context.task_ledger_path)
                incomplete_linked_tasks = []

                if ledger_path.exists():
                    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
                    tasks = {t["id"]: t for t in ledger.get("tasks", [])}

                    for msg in incomplete_messages:
                        for task_id in msg.linked_tasks:
                            task = tasks.get(task_id)
                            if task and task.get("state") != "completed":
                                incomplete_linked_tasks.append({
                                    "message_id": msg.message_id,
                                    "task_id": task_id,
                                    "task_state": task.get("state", "unknown"),
                                })

                if incomplete_linked_tasks:
                    return HookResult(
                        action=HookAction.CONTINUE,
                        reason="message_linked_tasks_incomplete",
                        confidence=1.0,
                        data={
                            "incomplete_count": len(incomplete_linked_tasks),
                            "incomplete_linked_tasks": incomplete_linked_tasks[:10],  # Limit for brevity
                        },
                        next_expected_state="message_linked_tasks_complete",
                    )

            # All message-linked tasks are complete
            return HookResult(
                action=HookAction.TERMINATE,
                reason="all_message_linked_tasks_complete",
                confidence=1.0,
                data={"message_count": len(self.message_store.messages)},
            )

        except Exception as e:
            # Error checking messages - continue to be safe
            return HookResult(
                action=HookAction.CONTINUE,
                reason="message_check_error",
                confidence=0.5,
                data={"error": str(e)},
            )

    def _check_tests(self, test_results: Dict[str, Any]) -> HookResult:
        """
        Check test results for success.

        If all tests pass, termination is allowed.
        """
        passed = test_results.get("passed", 0)
        failed = test_results.get("failed", 0)
        total = test_results.get("total", passed + failed)

        if failed == 0 and passed > 0:
            return HookResult(
                action=HookAction.TERMINATE,
                reason="all_tests_passed",
                confidence=1.0,
                data={
                    "passed": passed,
                    "total": total,
                },
            )

        return HookResult(
            action=HookAction.CONTINUE,
            reason="tests_failing",
            confidence=0.8,
            data={
                "passed": passed,
                "failed": failed,
                "total": total,
            },
            next_expected_state="tests_pass",
        )

    def _check_remediation(self, context: HookContext) -> Optional[HookResult]:
        """
        Check if there's a known remediation for the current failure.
        """
        # Look for error patterns in logs
        error_patterns = [
            "connection refused",
            "timeout",
            "rate limit",
            "out of memory",
        ]

        logs_text = "\n".join(context.logs).lower()

        for pattern in error_patterns:
            if pattern in logs_text:
                # Check retry count
                retry_key = f"{context.session_id}_{pattern}"
                current_retries = self.retry_counts.get(retry_key, 0)

                if current_retries < self.max_retries:
                    self.retry_counts[retry_key] = current_retries + 1

                    return HookResult(
                        action=HookAction.CONTINUE,
                        reason="known_error_with_remediation",
                        confidence=0.85,
                        data={
                            "error_pattern": pattern,
                            "retry_count": current_retries + 1,
                            "max_retries": self.max_retries,
                        },
                        next_expected_state="error_resolved",
                    )

        return None

    def _check_escalation(self, context: HookContext) -> Optional[HookResult]:
        """
        Check if escalation is needed for risky situations.
        """
        # Check for high cost operations
        if context.budget_spent > context.budget_limit * 0.8:
            return HookResult(
                action=HookAction.ESCALATE,
                reason="high_cost_operation",
                confidence=0.9,
                data={
                    "budget_spent": context.budget_spent,
                    "budget_limit": context.budget_limit,
                    "percentage_used": (context.budget_spent / context.budget_limit) * 100,
                },
            )

        # Check for destructive action patterns in logs
        destructive_patterns = [
            "delete",
            "drop",
            "remove",
            "destroy",
            "terminate",
            "kill",
        ]

        logs_text = "\n".join(context.logs).lower()

        for pattern in destructive_patterns:
            if pattern in logs_text:
                return HookResult(
                    action=HookAction.ESCALATE,
                    reason="potential_destructive_action",
                    confidence=0.75,
                    data={"pattern_detected": pattern},
                )

        return None
