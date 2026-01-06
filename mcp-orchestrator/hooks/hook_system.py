"""
Hook System

Hooks are triggered at specific points during task execution:
- BEFORE hooks: Run before a capability executes
- AFTER hooks: Run after a capability executes
- ON_ERROR hooks: Run when an error occurs
- ON_COMPLETE hooks: Run when a task completes

Hooks enable:
- TODO.md updates after each step
- Design pattern checking before code
- Test running after code changes
- Cache checking before API calls
- Web search for latest versions
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Awaitable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class HookTrigger(Enum):
    """When hooks are triggered."""
    BEFORE = "before"
    AFTER = "after"
    ON_ERROR = "on_error"
    ON_COMPLETE = "on_complete"


@dataclass
class HookResult:
    """Result of a hook execution."""
    hook_name: str
    success: bool
    output: Any
    error: Optional[str] = None
    duration_ms: int = 0


class Hook:
    """Base class for all hooks."""

    def __init__(self, name: str, trigger: HookTrigger, priority: int = 5):
        self.name = name
        self.trigger = trigger
        self.priority = priority  # 1-10, higher runs first

    async def execute(self, context: Dict[str, Any]) -> HookResult:
        """Execute the hook. Override in subclasses."""
        raise NotImplementedError


class UpdateTodoHook(Hook):
    """Updates TODO.md after each task step."""

    def __init__(self):
        super().__init__("update-todo", HookTrigger.AFTER, priority=10)
        self.todo_path = Path(__file__).parent.parent / "TODO.md"

    async def execute(self, context: Dict[str, Any]) -> HookResult:
        start = datetime.now()

        try:
            task_id = context.get("task_id")
            step_number = context.get("step_number")
            status = context.get("status", "done")
            result = context.get("result", "")

            if not self.todo_path.exists():
                return HookResult(self.name, True, "No TODO.md to update")

            content = self.todo_path.read_text()

            # Find the task section and update step status
            if task_id and step_number:
                # Update step status marker
                old_marker = f"{step_number}. [ ]"
                new_marker = f"{step_number}. [x]" if status == "done" else f"{step_number}. [!]"
                content = content.replace(old_marker, new_marker)

                # Also try with other markers
                for marker in ["[~]", "[T]"]:
                    content = content.replace(f"{step_number}. {marker}", new_marker)

                self.todo_path.write_text(content)

            duration = int((datetime.now() - start).total_seconds() * 1000)
            return HookResult(self.name, True, "TODO.md updated", duration_ms=duration)

        except Exception as e:
            return HookResult(self.name, False, None, str(e))


class CheckDesignPatternsHook(Hook):
    """Checks that code follows design patterns before execution."""

    def __init__(self):
        super().__init__("check-design-patterns", HookTrigger.BEFORE, priority=8)
        self.patterns_path = Path(__file__).parent.parent / "docs" / "PATTERNS.md"

    async def execute(self, context: Dict[str, Any]) -> HookResult:
        start = datetime.now()

        try:
            # Load patterns if they exist
            patterns = {}
            if self.patterns_path.exists():
                patterns["content"] = self.patterns_path.read_text()

            # Check what type of code is being written
            code_type = context.get("code_type", "general")

            guidance = {
                "patterns_loaded": self.patterns_path.exists(),
                "code_type": code_type,
                "recommendations": [],
            }

            # Add type-specific recommendations
            if code_type == "api":
                guidance["recommendations"].extend([
                    "Use consistent error handling",
                    "Include input validation",
                    "Add appropriate logging",
                    "Consider caching for expensive operations",
                ])
            elif code_type == "ui":
                guidance["recommendations"].extend([
                    "Follow design system",
                    "Ensure responsiveness",
                    "Use consistent styling",
                    "Add accessibility attributes",
                ])

            duration = int((datetime.now() - start).total_seconds() * 1000)
            return HookResult(self.name, True, guidance, duration_ms=duration)

        except Exception as e:
            return HookResult(self.name, False, None, str(e))


class LoadDesignSystemHook(Hook):
    """Loads UI design system before UI work."""

    def __init__(self):
        super().__init__("load-design-system", HookTrigger.BEFORE, priority=9)
        self.design_path = Path(__file__).parent.parent / "docs" / "DESIGN_SYSTEM.md"

    async def execute(self, context: Dict[str, Any]) -> HookResult:
        start = datetime.now()

        try:
            design_system = {
                "loaded": False,
                "guidelines": [],
            }

            if self.design_path.exists():
                content = self.design_path.read_text()
                design_system["loaded"] = True
                design_system["content"] = content

            # Default guidelines if no design system exists
            if not design_system["loaded"]:
                design_system["guidelines"] = [
                    "Use Tailwind CSS for styling",
                    "Mobile-first responsive design",
                    "Dark mode support (bg-gray-900, text-white)",
                    "Consistent spacing (p-4, m-4, gap-2)",
                    "Blue accent color (bg-blue-600, text-blue-400)",
                    "Rounded corners (rounded, rounded-lg)",
                    "Subtle shadows for depth",
                ]

            duration = int((datetime.now() - start).total_seconds() * 1000)
            return HookResult(self.name, True, design_system, duration_ms=duration)

        except Exception as e:
            return HookResult(self.name, False, None, str(e))


class RunTestsHook(Hook):
    """Runs tests after code changes."""

    def __init__(self):
        super().__init__("run-tests", HookTrigger.AFTER, priority=10)

    async def execute(self, context: Dict[str, Any]) -> HookResult:
        start = datetime.now()

        try:
            test_command = context.get("test_command", "pytest")
            project_path = context.get("project_path", Path.cwd())

            # Run the test command
            process = await asyncio.create_subprocess_shell(
                test_command,
                cwd=str(project_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=120
            )

            success = process.returncode == 0
            output = {
                "passed": success,
                "stdout": stdout.decode("utf-8"),
                "stderr": stderr.decode("utf-8"),
                "return_code": process.returncode,
            }

            duration = int((datetime.now() - start).total_seconds() * 1000)
            return HookResult(self.name, success, output, duration_ms=duration)

        except asyncio.TimeoutError:
            return HookResult(self.name, False, None, "Tests timed out after 2 minutes")
        except Exception as e:
            return HookResult(self.name, False, None, str(e))


class SearchLatestVersionHook(Hook):
    """Searches web for latest library/MCP versions."""

    def __init__(self):
        super().__init__("search-latest-version", HookTrigger.BEFORE, priority=9)

    async def execute(self, context: Dict[str, Any]) -> HookResult:
        start = datetime.now()

        try:
            library_name = context.get("library_name", "")
            if not library_name:
                return HookResult(self.name, True, {"skipped": True, "reason": "No library specified"})

            # Use web search to find latest version
            # This would integrate with the web-search skill
            search_query = f"{library_name} latest version npm pypi"

            result = {
                "library": library_name,
                "search_query": search_query,
                "recommendation": f"Search for '{search_query}' to get latest version",
            }

            duration = int((datetime.now() - start).total_seconds() * 1000)
            return HookResult(self.name, True, result, duration_ms=duration)

        except Exception as e:
            return HookResult(self.name, False, None, str(e))


class CheckCacheHook(Hook):
    """Checks cache before expensive operations."""

    def __init__(self):
        super().__init__("check-cache", HookTrigger.BEFORE, priority=7)
        self.cache_path = Path(__file__).parent.parent / "state" / "cache.json"

    async def execute(self, context: Dict[str, Any]) -> HookResult:
        start = datetime.now()

        try:
            cache_key = context.get("cache_key", "")
            if not cache_key:
                return HookResult(self.name, True, {"cached": False, "reason": "No cache key"})

            # Load cache
            cache = {}
            if self.cache_path.exists():
                cache = json.loads(self.cache_path.read_text())

            if cache_key in cache:
                entry = cache[cache_key]
                # Check if still valid (1 hour default)
                cached_at = datetime.fromisoformat(entry.get("cached_at", "2000-01-01"))
                age_hours = (datetime.now() - cached_at).total_seconds() / 3600

                if age_hours < 1:
                    return HookResult(self.name, True, {
                        "cached": True,
                        "data": entry.get("data"),
                        "age_hours": age_hours,
                    })

            duration = int((datetime.now() - start).total_seconds() * 1000)
            return HookResult(self.name, True, {"cached": False}, duration_ms=duration)

        except Exception as e:
            return HookResult(self.name, False, None, str(e))


class CheckCompletionHook(Hook):
    """Verifies task completion and outputs promise."""

    def __init__(self):
        super().__init__("check-completion", HookTrigger.ON_COMPLETE, priority=10)

    async def execute(self, context: Dict[str, Any]) -> HookResult:
        start = datetime.now()

        try:
            task_id = context.get("task_id")
            all_steps_done = context.get("all_steps_done", False)
            tests_passed = context.get("tests_passed", False)
            error = context.get("error")

            if error:
                promise = f"<Promise>BLOCKED: {error}</Promise>"
                success = False
            elif all_steps_done and tests_passed:
                promise = "<Promise>DONE</Promise>"
                success = True
            elif all_steps_done:
                promise = "<Promise>BLOCKED: Tests not passed</Promise>"
                success = False
            else:
                promise = "<Promise>BLOCKED: Not all steps completed</Promise>"
                success = False

            result = {
                "task_id": task_id,
                "promise": promise,
                "all_steps_done": all_steps_done,
                "tests_passed": tests_passed,
            }

            duration = int((datetime.now() - start).total_seconds() * 1000)
            return HookResult(self.name, success, result, duration_ms=duration)

        except Exception as e:
            return HookResult(self.name, False, None, str(e))


class HookSystem:
    """
    The Hook System - manages all hooks in the system.

    Hooks are triggered at specific points during task execution.
    """

    def __init__(self):
        self.hooks: Dict[str, Hook] = {}
        self._register_default_hooks()

    def _register_default_hooks(self):
        """Register all default hooks."""
        default_hooks = [
            UpdateTodoHook(),
            CheckDesignPatternsHook(),
            LoadDesignSystemHook(),
            RunTestsHook(),
            SearchLatestVersionHook(),
            CheckCacheHook(),
            CheckCompletionHook(),
        ]

        for hook in default_hooks:
            self.register(hook)

    def register(self, hook: Hook):
        """Register a hook."""
        self.hooks[hook.name] = hook

    def get(self, name: str) -> Optional[Hook]:
        """Get a hook by name."""
        return self.hooks.get(name)

    async def trigger(self, trigger_type: HookTrigger, hook_names: List[str], context: Dict[str, Any]) -> List[HookResult]:
        """
        Trigger multiple hooks of a specific type.

        Returns results in order of execution.
        """
        results = []

        # Filter hooks by trigger type and names
        hooks_to_run = [
            self.hooks[name]
            for name in hook_names
            if name in self.hooks and self.hooks[name].trigger == trigger_type
        ]

        # Sort by priority (higher first)
        hooks_to_run.sort(key=lambda h: h.priority, reverse=True)

        # Execute hooks
        for hook in hooks_to_run:
            result = await hook.execute(context)
            results.append(result)

            # Stop if hook failed and it's a BEFORE hook
            if not result.success and trigger_type == HookTrigger.BEFORE:
                break

        return results

    async def trigger_before(self, hook_names: List[str], context: Dict[str, Any]) -> List[HookResult]:
        """Trigger BEFORE hooks."""
        return await self.trigger(HookTrigger.BEFORE, hook_names, context)

    async def trigger_after(self, hook_names: List[str], context: Dict[str, Any]) -> List[HookResult]:
        """Trigger AFTER hooks."""
        return await self.trigger(HookTrigger.AFTER, hook_names, context)

    async def trigger_on_complete(self, context: Dict[str, Any]) -> HookResult:
        """Trigger completion check."""
        results = await self.trigger(HookTrigger.ON_COMPLETE, ["check-completion"], context)
        return results[0] if results else HookResult("check-completion", False, None, "No hook found")


# Singleton
_hook_system: Optional[HookSystem] = None


def get_hook_system() -> HookSystem:
    """Get the singleton Hook System."""
    global _hook_system
    if _hook_system is None:
        _hook_system = HookSystem()
    return _hook_system
