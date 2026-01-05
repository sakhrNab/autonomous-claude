"""
Pre-Step Hook

Runs BEFORE each agent step.

Uses:
- Permission checks
- Dry-run enforcement
- Budget checks
- Rate limiting
"""

from datetime import datetime
from typing import Any, Dict, Optional

from .base_hook import BaseHook, HookContext, HookResult, HookAction


class PreStepHook(BaseHook):
    """
    Pre-Step Hook - Validates before each step execution.

    This hook ensures:
    - The agent has permission for the action
    - Budget is sufficient
    - Rate limits are respected
    - Dry-run mode is enforced if enabled
    """

    name = "PreStepHook"
    description = "Validates conditions before each agent step"

    def __init__(
        self,
        dry_run: bool = False,
        required_permissions: Optional[Dict[str, list]] = None,
        rate_limits: Optional[Dict[str, int]] = None
    ):
        super().__init__()
        self.dry_run = dry_run
        self.required_permissions = required_permissions or {}
        self.rate_limits = rate_limits or {}
        self.rate_counters: Dict[str, list] = {}

    async def execute(self, context: HookContext) -> HookResult:
        """
        Execute pre-step validation.
        """
        # Check dry-run mode
        if self.dry_run:
            return HookResult(
                action=HookAction.SKIP,
                reason="dry_run_mode",
                confidence=1.0,
                data={"message": "Dry-run mode enabled, skipping execution"},
            )

        # Check permissions
        permission_check = self._check_permissions(context)
        if permission_check:
            self.record_result(permission_check)
            return permission_check

        # Check budget
        budget_check = self._check_budget(context)
        if budget_check:
            self.record_result(budget_check)
            return budget_check

        # Check rate limits
        rate_check = self._check_rate_limits(context)
        if rate_check:
            self.record_result(rate_check)
            return rate_check

        # All checks passed
        result = HookResult(
            action=HookAction.CONTINUE,
            reason="pre_step_checks_passed",
            confidence=1.0,
        )
        self.record_result(result)
        return result

    def _check_permissions(self, context: HookContext) -> Optional[HookResult]:
        """
        Check if the agent has required permissions.
        """
        agent_permissions = set(context.permissions)

        # Get required permissions for this agent
        required = self.required_permissions.get(context.agent_id, [])

        missing = [p for p in required if p not in agent_permissions]

        if missing:
            return HookResult(
                action=HookAction.TERMINATE,
                reason="permission_denied",
                confidence=1.0,
                data={
                    "agent_id": context.agent_id,
                    "missing_permissions": missing,
                },
            )

        return None

    def _check_budget(self, context: HookContext) -> Optional[HookResult]:
        """
        Check if there's sufficient budget for the next step.
        """
        budget_remaining = context.budget_limit - context.budget_spent

        # Estimate cost for next step (placeholder - would be more sophisticated)
        estimated_cost = 0.10

        if budget_remaining < estimated_cost:
            return HookResult(
                action=HookAction.ESCALATE,
                reason="insufficient_budget",
                confidence=0.95,
                data={
                    "budget_remaining": budget_remaining,
                    "estimated_cost": estimated_cost,
                },
            )

        # Warn if budget is low
        if budget_remaining < context.budget_limit * 0.2:
            # Continue but log warning
            pass

        return None

    def _check_rate_limits(self, context: HookContext) -> Optional[HookResult]:
        """
        Check rate limits for the agent.
        """
        agent_id = context.agent_id
        now = datetime.now()

        # Get rate limit for this agent
        limit = self.rate_limits.get(agent_id, 100)  # Default 100/minute

        # Initialize counter if needed
        if agent_id not in self.rate_counters:
            self.rate_counters[agent_id] = []

        # Clean old entries (older than 1 minute)
        self.rate_counters[agent_id] = [
            ts for ts in self.rate_counters[agent_id]
            if (now - ts).total_seconds() < 60
        ]

        # Check if rate limit exceeded
        if len(self.rate_counters[agent_id]) >= limit:
            return HookResult(
                action=HookAction.RETRY,
                reason="rate_limit_exceeded",
                confidence=1.0,
                data={
                    "current_rate": len(self.rate_counters[agent_id]),
                    "limit": limit,
                    "wait_seconds": 60,
                },
            )

        # Record this request
        self.rate_counters[agent_id].append(now)

        return None

    def set_dry_run(self, enabled: bool):
        """Enable or disable dry-run mode."""
        self.dry_run = enabled

    def add_permission_requirement(self, agent_id: str, permissions: list):
        """Add permission requirements for an agent."""
        self.required_permissions[agent_id] = permissions

    def set_rate_limit(self, agent_id: str, limit: int):
        """Set rate limit for an agent."""
        self.rate_limits[agent_id] = limit
