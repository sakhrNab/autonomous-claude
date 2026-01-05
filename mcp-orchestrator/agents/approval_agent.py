"""
Approval Agent

RESPONSIBILITY: Human approval workflow.

This agent:
- Asks for human approval
- Pauses execution
- Resumes or terminates based on response

Used for:
- Costly actions
- Destructive actions
- Policy violations
- Unknown/risky situations
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import asyncio

from .base_agent import BaseAgent, AgentContext, AgentResult


class ApprovalStatus(Enum):
    """Status of an approval request."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


@dataclass
class ApprovalRequest:
    """A request for human approval."""
    request_id: str
    action: str
    reason: str
    risk_level: str
    estimated_cost: float
    status: ApprovalStatus
    created_at: datetime
    responded_at: Optional[datetime] = None
    responder: Optional[str] = None
    response_notes: Optional[str] = None


class ApprovalAgent(BaseAgent):
    """
    Approval Agent - Manages human approval workflows.

    This agent:
    - Creates approval requests
    - Waits for human response
    - Enforces timeout policies
    - Unblocks tasks after approval
    """

    def __init__(self, timeout_seconds: int = 3600):
        super().__init__(name="ApprovalAgent")
        self.timeout_seconds = timeout_seconds
        self.pending_requests: Dict[str, ApprovalRequest] = {}
        self.approval_history: List[ApprovalRequest] = []

    async def perform_step(self, context: AgentContext) -> AgentResult:
        """
        Handle approval workflow.
        """
        self.iteration_count += 1

        action = context.plan.get("action", "request") if context.plan else "request"

        if action == "request":
            return await self._create_request(context)
        elif action == "check":
            return await self._check_status(context)
        elif action == "respond":
            return await self._process_response(context)
        elif action == "list_pending":
            return self._list_pending()
        else:
            return AgentResult(
                success=False,
                error=f"Unknown action: {action}",
            )

    async def _create_request(self, context: AgentContext) -> AgentResult:
        """
        Create a new approval request.
        """
        import uuid

        action_desc = context.plan.get("action_description", "Unknown action") if context.plan else "Unknown action"
        reason = context.plan.get("reason", "Requires approval") if context.plan else "Requires approval"
        risk_level = context.plan.get("risk_level", "medium") if context.plan else "medium"
        estimated_cost = context.plan.get("estimated_cost", 0.0) if context.plan else 0.0

        request_id = str(uuid.uuid4())[:8]

        request = ApprovalRequest(
            request_id=request_id,
            action=action_desc,
            reason=reason,
            risk_level=risk_level,
            estimated_cost=estimated_cost,
            status=ApprovalStatus.PENDING,
            created_at=datetime.now(),
        )

        self.pending_requests[request_id] = request

        self.log("info", "Approval request created", {
            "request_id": request_id,
            "action": action_desc,
            "risk_level": risk_level,
        })

        # In production, this would send notification to approvers
        await self._notify_approvers(request)

        return AgentResult(
            success=True,
            data={
                "request_id": request_id,
                "status": ApprovalStatus.PENDING.value,
                "message": "Awaiting human approval",
            },
            metadata={"waiting_for_approval": True},
        )

    async def _check_status(self, context: AgentContext) -> AgentResult:
        """
        Check status of an approval request.
        """
        request_id = context.plan.get("request_id") if context.plan else None

        if not request_id or request_id not in self.pending_requests:
            return AgentResult(
                success=False,
                error=f"Request not found: {request_id}",
            )

        request = self.pending_requests[request_id]

        # Check for timeout
        elapsed = (datetime.now() - request.created_at).total_seconds()
        if elapsed > self.timeout_seconds and request.status == ApprovalStatus.PENDING:
            request.status = ApprovalStatus.TIMEOUT
            self._archive_request(request_id)

            return AgentResult(
                success=False,
                error="Approval request timed out",
                data={
                    "request_id": request_id,
                    "status": ApprovalStatus.TIMEOUT.value,
                    "elapsed_seconds": elapsed,
                },
            )

        return AgentResult(
            success=request.status == ApprovalStatus.APPROVED,
            data={
                "request_id": request_id,
                "status": request.status.value,
                "elapsed_seconds": elapsed,
            },
        )

    async def _process_response(self, context: AgentContext) -> AgentResult:
        """
        Process an approval response.
        """
        request_id = context.plan.get("request_id") if context.plan else None
        approved = context.plan.get("approved", False) if context.plan else False
        responder = context.plan.get("responder", "unknown") if context.plan else "unknown"
        notes = context.plan.get("notes") if context.plan else None

        if not request_id or request_id not in self.pending_requests:
            return AgentResult(
                success=False,
                error=f"Request not found: {request_id}",
            )

        request = self.pending_requests[request_id]
        request.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
        request.responded_at = datetime.now()
        request.responder = responder
        request.response_notes = notes

        self.log("info", f"Approval {'granted' if approved else 'rejected'}", {
            "request_id": request_id,
            "responder": responder,
        })

        self._archive_request(request_id)

        return AgentResult(
            success=approved,
            data={
                "request_id": request_id,
                "approved": approved,
                "responder": responder,
            },
        )

    def _list_pending(self) -> AgentResult:
        """List all pending approval requests."""
        pending = [
            {
                "request_id": req.request_id,
                "action": req.action,
                "risk_level": req.risk_level,
                "created_at": req.created_at.isoformat(),
                "elapsed_seconds": (datetime.now() - req.created_at).total_seconds(),
            }
            for req in self.pending_requests.values()
        ]

        return AgentResult(
            success=True,
            data={
                "pending_requests": pending,
                "count": len(pending),
            },
        )

    def _archive_request(self, request_id: str):
        """Move a request from pending to history."""
        if request_id in self.pending_requests:
            request = self.pending_requests.pop(request_id)
            self.approval_history.append(request)

    async def _notify_approvers(self, request: ApprovalRequest):
        """
        Send notification to approvers.

        In production, this would:
        - Send Slack message
        - Send email
        - Update UI
        - Maybe send voice notification
        """
        self.log("info", "Notifying approvers", {
            "request_id": request.request_id,
        })
        # Placeholder for actual notification logic

    async def wait_for_approval(
        self,
        request_id: str,
        poll_interval: int = 5
    ) -> AgentResult:
        """
        Wait for an approval request to be resolved.
        """
        while True:
            if request_id not in self.pending_requests:
                # Check history for result
                for req in self.approval_history:
                    if req.request_id == request_id:
                        return AgentResult(
                            success=req.status == ApprovalStatus.APPROVED,
                            data={
                                "request_id": request_id,
                                "status": req.status.value,
                            },
                        )

            request = self.pending_requests.get(request_id)
            if request:
                # Check timeout
                elapsed = (datetime.now() - request.created_at).total_seconds()
                if elapsed > self.timeout_seconds:
                    request.status = ApprovalStatus.TIMEOUT
                    self._archive_request(request_id)
                    return AgentResult(
                        success=False,
                        error="Approval timed out",
                    )

            await asyncio.sleep(poll_interval)
