"""
Approval Hook

Blocks execution until human approves or rejects.

Used for:
- Costly actions (above threshold)
- Destructive actions
- Policy violations
- Unknown/risky situations
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import asyncio

from .base_hook import BaseHook, HookContext, HookResult, HookAction


class ApprovalHook(BaseHook):
    """
    Approval Hook - Blocks execution pending human approval.

    This hook:
    - Pauses execution for risky actions
    - Waits for human approval
    - Times out if no response
    - Records approval decisions
    """

    name = "ApprovalHook"
    description = "Blocks execution until human approves or rejects"

    def __init__(
        self,
        cost_threshold: float = 50.0,
        timeout_seconds: int = 3600,
        auto_approve_safe: bool = False
    ):
        super().__init__()
        self.cost_threshold = cost_threshold
        self.timeout_seconds = timeout_seconds
        self.auto_approve_safe = auto_approve_safe
        self.pending_approvals: Dict[str, Dict[str, Any]] = {}
        self.approval_history: List[Dict[str, Any]] = []

    async def execute(self, context: HookContext) -> HookResult:
        """
        Execute approval check.
        """
        # Check if approval is needed
        needs_approval, reason = self._needs_approval(context)

        if not needs_approval:
            result = HookResult(
                action=HookAction.CONTINUE,
                reason="approval_not_required",
                confidence=1.0,
            )
            self.record_result(result)
            return result

        # Create approval request
        request_id = f"approval_{context.session_id}_{context.iteration}"

        self.pending_approvals[request_id] = {
            "request_id": request_id,
            "session_id": context.session_id,
            "agent_id": context.agent_id,
            "reason": reason,
            "created_at": datetime.now().isoformat(),
            "status": "pending",
            "context": {
                "iteration": context.iteration,
                "budget_spent": context.budget_spent,
                "elapsed_time": context.elapsed_time_seconds,
            },
        }

        # Wait for approval
        result = await self._wait_for_approval(request_id)

        # Clean up
        if request_id in self.pending_approvals:
            del self.pending_approvals[request_id]

        self.record_result(result)
        return result

    def _needs_approval(self, context: HookContext) -> tuple[bool, str]:
        """
        Determine if approval is needed.
        """
        # Check cost threshold
        if context.budget_spent > self.cost_threshold:
            return True, f"Cost exceeds threshold (${context.budget_spent:.2f} > ${self.cost_threshold:.2f})"

        # Check for destructive patterns in logs
        destructive_keywords = ["delete", "drop", "remove", "destroy", "terminate"]
        logs_text = " ".join(context.logs).lower()

        for keyword in destructive_keywords:
            if keyword in logs_text:
                return True, f"Destructive action detected: {keyword}"

        # Check permissions for risky operations
        risky_permissions = ["admin:write", "data:delete", "system:modify"]
        for perm in risky_permissions:
            if perm in context.permissions:
                return True, f"Risky permission in use: {perm}"

        return False, ""

    async def _wait_for_approval(self, request_id: str) -> HookResult:
        """
        Wait for human approval.
        """
        start_time = datetime.now()

        # In production, would:
        # 1. Send notification to approvers
        # 2. Poll for response
        # 3. Handle timeout

        # For now, simulate waiting
        while True:
            elapsed = (datetime.now() - start_time).total_seconds()

            # Check timeout
            if elapsed >= self.timeout_seconds:
                self._record_approval(request_id, "timeout", None)
                return HookResult(
                    action=HookAction.TERMINATE,
                    reason="approval_timeout",
                    confidence=1.0,
                    data={
                        "request_id": request_id,
                        "timeout_seconds": self.timeout_seconds,
                    },
                )

            # Check if approval was received (simulated)
            if request_id in self.pending_approvals:
                status = self.pending_approvals[request_id].get("status")

                if status == "approved":
                    self._record_approval(request_id, "approved", "user")
                    return HookResult(
                        action=HookAction.CONTINUE,
                        reason="approval_granted",
                        confidence=1.0,
                        data={"request_id": request_id},
                    )
                elif status == "rejected":
                    self._record_approval(request_id, "rejected", "user")
                    return HookResult(
                        action=HookAction.TERMINATE,
                        reason="approval_rejected",
                        confidence=1.0,
                        data={"request_id": request_id},
                    )

            # Wait before next check
            await asyncio.sleep(1)

            # Auto-approve if configured and safe (for testing)
            if self.auto_approve_safe and elapsed > 5:
                self._record_approval(request_id, "auto_approved", "system")
                return HookResult(
                    action=HookAction.CONTINUE,
                    reason="auto_approved",
                    confidence=0.9,
                    data={"request_id": request_id},
                )

    def _record_approval(self, request_id: str, decision: str, approver: Optional[str]):
        """
        Record approval decision for audit.
        """
        self.approval_history.append({
            "request_id": request_id,
            "decision": decision,
            "approver": approver,
            "timestamp": datetime.now().isoformat(),
        })

    def approve(self, request_id: str, approver: str = "user"):
        """
        Manually approve a pending request.
        """
        if request_id in self.pending_approvals:
            self.pending_approvals[request_id]["status"] = "approved"
            self.pending_approvals[request_id]["approver"] = approver
            self.pending_approvals[request_id]["responded_at"] = datetime.now().isoformat()

    def reject(self, request_id: str, approver: str = "user", reason: str = ""):
        """
        Manually reject a pending request.
        """
        if request_id in self.pending_approvals:
            self.pending_approvals[request_id]["status"] = "rejected"
            self.pending_approvals[request_id]["approver"] = approver
            self.pending_approvals[request_id]["rejection_reason"] = reason
            self.pending_approvals[request_id]["responded_at"] = datetime.now().isoformat()

    def get_pending_approvals(self) -> List[Dict[str, Any]]:
        """Get all pending approval requests."""
        return list(self.pending_approvals.values())

    def get_approval_history(self) -> List[Dict[str, Any]]:
        """Get approval history for audit."""
        return self.approval_history.copy()
