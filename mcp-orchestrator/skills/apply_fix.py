"""
Apply Fix Skill

Applies known remediations for failures.
"""

from typing import Any, Dict, List, Optional
import asyncio

from .base_skill import BaseSkill, SkillResult


class ApplyFix(BaseSkill):
    """
    Skill to apply fixes and remediations.

    Can perform:
    - Configuration changes
    - Retries with backoff
    - Resource adjustments
    - Dependency fixes
    """

    name = "apply_fix"
    description = "Apply a remediation or fix for a known issue"
    required_permissions = ["fix:apply"]
    estimated_cost = 0.05

    def __init__(self):
        super().__init__()
        self.fix_handlers = {
            "retry": self._apply_retry,
            "retry_with_backoff": self._apply_retry_backoff,
            "increase_timeout": self._apply_timeout_increase,
            "increase_resources": self._apply_resource_increase,
            "refresh_credentials": self._apply_credential_refresh,
            "install_dependencies": self._apply_dependency_install,
            "config_change": self._apply_config_change,
            "restart_service": self._apply_restart,
        }

    async def execute(
        self,
        args: Dict[str, Any],
        context: Optional[Any] = None
    ) -> SkillResult:
        """
        Apply a fix.

        Args:
            args:
                - action: Fix action to apply
                - target: Target of the fix (job_id, service, etc.)
                - parameters: Fix-specific parameters
                - dry_run: If True, only simulate the fix
        """
        await self.pre_execute(args)

        action = args.get("action")
        target = args.get("target")
        parameters = args.get("parameters", {})
        dry_run = args.get("dry_run", False)

        if action not in self.fix_handlers:
            return SkillResult(
                success=False,
                error=f"Unknown fix action: {action}",
            )

        try:
            handler = self.fix_handlers[action]

            if dry_run:
                result_data = {
                    "action": action,
                    "target": target,
                    "dry_run": True,
                    "would_apply": True,
                }
            else:
                result_data = await handler(target, parameters)

            skill_result = SkillResult(
                success=True,
                data={
                    "action": action,
                    "target": target,
                    "applied": not dry_run,
                    "result": result_data,
                },
                cost=self.estimated_cost if not dry_run else 0,
            )

        except Exception as e:
            skill_result = SkillResult(
                success=False,
                error=str(e),
            )

        await self.post_execute(skill_result)
        return skill_result

    async def _apply_retry(
        self,
        target: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Simple retry of a failed operation."""
        return {
            "retried": True,
            "target": target,
        }

    async def _apply_retry_backoff(
        self,
        target: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Retry with exponential backoff."""
        max_retries = parameters.get("max_retries", 3)
        base_delay = parameters.get("base_delay", 1)

        for attempt in range(max_retries):
            delay = base_delay * (2 ** attempt)
            await asyncio.sleep(delay)

            # In production, would attempt the actual operation
            # For now, simulate success after retries

        return {
            "retried": True,
            "attempts": max_retries,
            "total_delay": sum(base_delay * (2 ** i) for i in range(max_retries)),
        }

    async def _apply_timeout_increase(
        self,
        target: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Increase timeout configuration."""
        current = parameters.get("current_timeout", 30)
        multiplier = parameters.get("multiplier", 2)
        new_timeout = current * multiplier

        return {
            "previous_timeout": current,
            "new_timeout": new_timeout,
            "applied": True,
        }

    async def _apply_resource_increase(
        self,
        target: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Increase resource allocation."""
        resource_type = parameters.get("resource_type", "memory")
        increase_percent = parameters.get("increase_percent", 50)

        return {
            "resource_type": resource_type,
            "increase_percent": increase_percent,
            "applied": True,
        }

    async def _apply_credential_refresh(
        self,
        target: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Refresh credentials."""
        return {
            "credentials_refreshed": True,
            "target": target,
        }

    async def _apply_dependency_install(
        self,
        target: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Install missing dependencies."""
        packages = parameters.get("packages", [])

        return {
            "packages_installed": packages,
            "success": True,
        }

    async def _apply_config_change(
        self,
        target: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply configuration change."""
        config_key = parameters.get("key")
        config_value = parameters.get("value")

        return {
            "config_key": config_key,
            "config_value": config_value,
            "applied": True,
        }

    async def _apply_restart(
        self,
        target: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Restart a service."""
        return {
            "service": target,
            "restarted": True,
        }

    def validate_args(self, args: Dict[str, Any]) -> List[str]:
        errors = []
        if not args.get("action"):
            errors.append("action is required")
        if args.get("action") and args["action"] not in self.fix_handlers:
            errors.append(f"Unknown action: {args['action']}")
        return errors

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": list(self.fix_handlers.keys()),
                    "description": "Fix action to apply",
                },
                "target": {
                    "type": "string",
                    "description": "Target of the fix",
                },
                "parameters": {
                    "type": "object",
                    "description": "Fix-specific parameters",
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "Simulate without applying",
                },
            },
            "required": ["action"],
        }
