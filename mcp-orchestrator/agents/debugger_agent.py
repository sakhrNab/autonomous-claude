"""
Debugger Agent

RESPONSIBILITY: Analyze and fix failures.

This agent:
- Analyzes failures
- Reads logs
- Proposes fixes
- Applies fixes via skills

Triggered when:
- Execution fails
- Tests fail
- Stop hook requests remediation
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import re

from .base_agent import BaseAgent, AgentContext, AgentResult


@dataclass
class ErrorPattern:
    """A known error pattern with remediation."""
    pattern: str
    error_type: str
    remediation: str
    skill: str
    args: Dict[str, Any]
    confidence: float = 0.8


class DebuggerAgent(BaseAgent):
    """
    Debugger Agent - Analyzes failures and applies fixes.

    This agent is the troubleshooter that:
    - Identifies root causes
    - Matches known error patterns
    - Proposes and applies fixes
    """

    def __init__(self):
        super().__init__(name="DebuggerAgent")
        self.error_patterns = self._load_error_patterns()
        self.fix_history: List[Dict[str, Any]] = []

    def _load_error_patterns(self) -> List[ErrorPattern]:
        """Load known error patterns and their remediations."""
        return [
            ErrorPattern(
                pattern=r"connection refused",
                error_type="connectivity",
                remediation="Check service availability and retry",
                skill="apply_fix",
                args={"action": "retry_with_backoff"},
                confidence=0.9,
            ),
            ErrorPattern(
                pattern=r"timeout",
                error_type="timeout",
                remediation="Increase timeout and retry",
                skill="apply_fix",
                args={"action": "increase_timeout"},
                confidence=0.85,
            ),
            ErrorPattern(
                pattern=r"permission denied|unauthorized|403",
                error_type="permission",
                remediation="Check credentials and permissions",
                skill="apply_fix",
                args={"action": "refresh_credentials"},
                confidence=0.75,
            ),
            ErrorPattern(
                pattern=r"out of memory|oom|memory exhausted",
                error_type="resource",
                remediation="Increase memory allocation",
                skill="apply_fix",
                args={"action": "increase_resources"},
                confidence=0.8,
            ),
            ErrorPattern(
                pattern=r"rate limit|too many requests|429",
                error_type="rate_limit",
                remediation="Apply exponential backoff",
                skill="apply_fix",
                args={"action": "backoff_retry"},
                confidence=0.95,
            ),
            ErrorPattern(
                pattern=r"test failed|assertion error|expected .* but got",
                error_type="test_failure",
                remediation="Analyze test output and fix code",
                skill="apply_fix",
                args={"action": "analyze_test_failure"},
                confidence=0.7,
            ),
            ErrorPattern(
                pattern=r"import error|module not found|no module named",
                error_type="dependency",
                remediation="Install missing dependencies",
                skill="apply_fix",
                args={"action": "install_dependencies"},
                confidence=0.9,
            ),
            ErrorPattern(
                pattern=r"syntax error|parsing error",
                error_type="syntax",
                remediation="Fix syntax error in code",
                skill="apply_fix",
                args={"action": "fix_syntax"},
                confidence=0.6,
            ),
        ]

    async def perform_step(self, context: AgentContext) -> AgentResult:
        """
        Analyze a failure and propose/apply fixes.
        """
        self.iteration_count += 1

        action = context.plan.get("action", "analyze") if context.plan else "analyze"

        if action == "analyze":
            return await self._analyze_failure(context)
        elif action == "apply_fix":
            return await self._apply_fix(context)
        elif action == "get_history":
            return self._get_fix_history()
        else:
            return AgentResult(
                success=False,
                error=f"Unknown action: {action}",
            )

    async def _analyze_failure(self, context: AgentContext) -> AgentResult:
        """
        Analyze a failure and identify potential fixes.
        """
        logs = context.plan.get("logs", "") if context.plan else ""
        error_message = context.plan.get("error", "") if context.plan else ""

        combined_text = f"{logs}\n{error_message}".lower()

        # Find matching patterns
        matches = []
        for pattern in self.error_patterns:
            if re.search(pattern.pattern, combined_text, re.IGNORECASE):
                matches.append({
                    "error_type": pattern.error_type,
                    "pattern": pattern.pattern,
                    "remediation": pattern.remediation,
                    "skill": pattern.skill,
                    "args": pattern.args,
                    "confidence": pattern.confidence,
                })

        if not matches:
            self.log("warning", "No known error pattern matched", {
                "error_preview": error_message[:200] if error_message else "no error",
            })
            return AgentResult(
                success=False,
                error="Unknown error pattern - requires manual investigation",
                data={
                    "matches": [],
                    "raw_error": error_message[:500],
                    "requires_escalation": True,
                },
            )

        # Sort by confidence
        matches.sort(key=lambda x: x["confidence"], reverse=True)
        best_match = matches[0]

        self.log("info", "Error pattern identified", {
            "error_type": best_match["error_type"],
            "confidence": best_match["confidence"],
        })

        return AgentResult(
            success=True,
            data={
                "matches": matches,
                "best_match": best_match,
                "recommended_action": {
                    "skill": best_match["skill"],
                    "args": best_match["args"],
                    "confidence": best_match["confidence"],
                },
            },
            next_action="apply_fix" if best_match["confidence"] >= 0.7 else "escalate",
        )

    async def _apply_fix(self, context: AgentContext) -> AgentResult:
        """
        Apply a fix based on analysis.
        """
        fix_action = context.plan.get("fix_action") if context.plan else None
        args = context.plan.get("args", {}) if context.plan else {}

        if not fix_action:
            return AgentResult(
                success=False,
                error="No fix action specified",
            )

        self.log("info", f"Applying fix: {fix_action}", {"args": args})

        # Record the fix attempt
        fix_record = {
            "action": fix_action,
            "args": args,
            "timestamp": self.last_activity.isoformat(),
            "result": None,
        }

        try:
            result = await self._execute_fix(fix_action, args)
            fix_record["result"] = "success" if result else "failed"
            self.fix_history.append(fix_record)

            return AgentResult(
                success=result,
                data={
                    "fix_applied": fix_action,
                    "result": "success" if result else "failed",
                },
            )
        except Exception as e:
            fix_record["result"] = f"error: {str(e)}"
            self.fix_history.append(fix_record)

            return AgentResult(
                success=False,
                error=str(e),
            )

    async def _execute_fix(self, action: str, args: Dict[str, Any]) -> bool:
        """
        Execute a specific fix action.

        In production, this would dispatch to the appropriate skill.
        """
        # Map of fix actions to their implementations
        fix_handlers = {
            "retry_with_backoff": self._fix_retry,
            "increase_timeout": self._fix_timeout,
            "refresh_credentials": self._fix_credentials,
            "increase_resources": self._fix_resources,
            "backoff_retry": self._fix_backoff,
            "install_dependencies": self._fix_dependencies,
            "fix_syntax": self._fix_syntax,
            "analyze_test_failure": self._fix_test,
        }

        handler = fix_handlers.get(action)
        if handler:
            return await handler(args)

        self.log("warning", f"Unknown fix action: {action}")
        return False

    async def _fix_retry(self, args: Dict[str, Any]) -> bool:
        """Simple retry with exponential backoff."""
        self.log("info", "Executing retry with backoff")
        return True

    async def _fix_timeout(self, args: Dict[str, Any]) -> bool:
        """Increase timeout configuration."""
        self.log("info", "Increasing timeout")
        return True

    async def _fix_credentials(self, args: Dict[str, Any]) -> bool:
        """Refresh credentials."""
        self.log("info", "Refreshing credentials")
        return True

    async def _fix_resources(self, args: Dict[str, Any]) -> bool:
        """Increase resource allocation."""
        self.log("info", "Increasing resources")
        return True

    async def _fix_backoff(self, args: Dict[str, Any]) -> bool:
        """Apply exponential backoff for rate limiting."""
        self.log("info", "Applying backoff strategy")
        return True

    async def _fix_dependencies(self, args: Dict[str, Any]) -> bool:
        """Install missing dependencies."""
        self.log("info", "Installing dependencies")
        return True

    async def _fix_syntax(self, args: Dict[str, Any]) -> bool:
        """Fix syntax errors."""
        self.log("info", "Fixing syntax errors")
        return True

    async def _fix_test(self, args: Dict[str, Any]) -> bool:
        """Analyze and fix test failures."""
        self.log("info", "Analyzing test failure")
        return True

    def _get_fix_history(self) -> AgentResult:
        """Return the history of applied fixes."""
        return AgentResult(
            success=True,
            data={"fix_history": self.fix_history},
        )
