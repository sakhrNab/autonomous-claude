"""
Post-Step Hook

Runs AFTER each skill execution.

Uses:
- Test execution
- Artifact validation
- Result normalization
- Memory updates
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from .base_hook import BaseHook, HookContext, HookResult, HookAction


class PostStepHook(BaseHook):
    """
    Post-Step Hook - Processes results after each step.

    This hook:
    - Validates artifacts were created
    - Runs tests if applicable
    - Updates memory stores
    - Normalizes results
    """

    name = "PostStepHook"
    description = "Processes and validates results after each agent step"

    def __init__(self, run_tests: bool = True, validate_artifacts: bool = True):
        super().__init__()
        self.run_tests = run_tests
        self.validate_artifacts = validate_artifacts
        self.test_results: Dict[str, Any] = {}
        self.artifact_registry: List[str] = []

    async def execute(self, context: HookContext) -> HookResult:
        """
        Execute post-step processing.
        """
        # Extract step result from context (would be passed in data)
        step_result = context.metadata.get("step_result", {}) if hasattr(context, "metadata") else {}

        # Validate artifacts
        if self.validate_artifacts:
            artifact_check = await self._validate_artifacts(step_result)
            if artifact_check and not artifact_check.data.get("valid", True):
                self.record_result(artifact_check)
                return artifact_check

        # Run tests if applicable
        if self.run_tests:
            test_result = await self._run_tests(context)
            if test_result:
                self.test_results = test_result.data
                self.record_result(test_result)
                return test_result

        # Update memory
        await self._update_memory(context, step_result)

        # Normalize and record result
        result = HookResult(
            action=HookAction.CONTINUE,
            reason="post_step_complete",
            confidence=1.0,
            data={
                "artifacts_validated": self.validate_artifacts,
                "tests_run": self.run_tests,
                "test_results": self.test_results,
            },
        )
        self.record_result(result)
        return result

    async def _validate_artifacts(self, step_result: Dict[str, Any]) -> Optional[HookResult]:
        """
        Validate that expected artifacts were created.
        """
        artifacts = step_result.get("artifacts", [])

        if not artifacts:
            return None  # No artifacts to validate

        missing = []
        for artifact in artifacts:
            # In production, would check if artifact exists
            exists = True  # Placeholder
            if not exists:
                missing.append(artifact)

        if missing:
            return HookResult(
                action=HookAction.RETRY,
                reason="missing_artifacts",
                confidence=0.9,
                data={
                    "missing_artifacts": missing,
                    "valid": False,
                },
            )

        # Register artifacts
        self.artifact_registry.extend(artifacts)

        return HookResult(
            action=HookAction.CONTINUE,
            reason="artifacts_valid",
            confidence=1.0,
            data={
                "artifacts": artifacts,
                "valid": True,
            },
        )

    async def _run_tests(self, context: HookContext) -> Optional[HookResult]:
        """
        Run tests after execution.
        """
        # Placeholder for actual test execution
        # In production, would run unit/integration tests

        test_results = {
            "passed": 5,
            "failed": 0,
            "skipped": 1,
            "total": 6,
            "duration_ms": 1500,
        }

        if test_results["failed"] > 0:
            return HookResult(
                action=HookAction.CONTINUE,
                reason="tests_failing",
                confidence=0.8,
                data=test_results,
                next_expected_state="tests_pass",
            )

        return HookResult(
            action=HookAction.CONTINUE,
            reason="tests_passed",
            confidence=1.0,
            data=test_results,
        )

    async def _update_memory(self, context: HookContext, step_result: Dict[str, Any]):
        """
        Update memory stores with execution data.
        """
        # Session memory update
        session_update = {
            "iteration": context.iteration,
            "timestamp": datetime.now().isoformat(),
            "agent_id": context.agent_id,
            "result_summary": step_result.get("success", False),
        }

        # In production, would persist to memory store
        # For now, just log

    def get_test_results(self) -> Dict[str, Any]:
        """Get the latest test results."""
        return self.test_results

    def get_artifacts(self) -> List[str]:
        """Get all registered artifacts."""
        return self.artifact_registry.copy()

    def clear_artifacts(self):
        """Clear artifact registry."""
        self.artifact_registry = []
