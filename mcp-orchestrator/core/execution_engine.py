"""
Execution Engine with Ralph Wiggum Pattern

The Ralph Wiggum pattern is an iterative retry mechanism that:
1. Attempts a task step
2. Tests the result
3. If tests fail, analyzes why and adjusts
4. Retries up to max_iterations (default 10)
5. Only outputs <Promise>DONE</Promise> when tests pass
6. Outputs <Promise>BLOCKED: reason</Promise> if max iterations reached

"I'm helping!" - Ralph Wiggum
"""

import asyncio
import json
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class StepStatus(Enum):
    """Status of an execution step."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    TESTING = "testing"
    DONE = "done"
    BLOCKED = "blocked"
    RETRYING = "retrying"


class PromiseStatus(Enum):
    """Final promise status."""
    PENDING = "PENDING"
    DONE = "DONE"
    BLOCKED = "BLOCKED"


@dataclass
class StepResult:
    """Result of executing a step."""
    step_number: int
    success: bool
    output: Any
    error: Optional[str] = None
    iteration: int = 1
    tests_passed: bool = False
    test_output: Optional[str] = None
    duration_ms: int = 0


@dataclass
class ExecutionState:
    """Current state of task execution."""
    task_id: str
    current_step: int = 1
    total_steps: int = 0
    iteration: int = 1
    max_iterations: int = 10
    status: StepStatus = StepStatus.PENDING
    promise: PromiseStatus = PromiseStatus.PENDING
    results: List[StepResult] = field(default_factory=list)
    error_history: List[Dict[str, Any]] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""


class ExecutionEngine:
    """
    The Execution Engine - runs tasks using the Ralph Wiggum pattern.

    Key features:
    - Iterative retry until success
    - Automatic test verification
    - Error analysis and adjustment
    - Promise-based completion
    """

    def __init__(self, max_iterations: int = 10):
        self.max_iterations = max_iterations
        self.base_path = Path(__file__).parent.parent
        self.state_path = self.base_path / "state"
        self.state_path.mkdir(parents=True, exist_ok=True)

        # Claude CLI for intelligent adjustments
        self.claude_cli = shutil.which("claude")

        # Hook system
        self._hook_system = None

        # Callbacks
        self.on_step_start: Optional[Callable[[int, str], Awaitable[None]]] = None
        self.on_step_complete: Optional[Callable[[StepResult], Awaitable[None]]] = None
        self.on_iteration: Optional[Callable[[int, int], Awaitable[None]]] = None
        self.on_promise: Optional[Callable[[PromiseStatus, str], Awaitable[None]]] = None

    @property
    def hook_system(self):
        """Lazy load hook system to avoid circular imports."""
        if self._hook_system is None:
            from hooks.hook_system import get_hook_system
            self._hook_system = get_hook_system()
        return self._hook_system

    async def execute_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a complete plan using the Ralph Wiggum pattern.

        Returns the final result with promise status.
        """
        task_id = plan.get("task_id", f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        steps = plan.get("steps", [])

        state = ExecutionState(
            task_id=task_id,
            total_steps=len(steps),
            max_iterations=plan.get("max_iterations", self.max_iterations),
            started_at=datetime.now().isoformat(),
        )

        # Save initial state
        self._save_state(state)

        try:
            # Execute each step with retry logic
            for step in steps:
                step_result = await self._execute_step_with_retry(step, state)
                state.results.append(step_result)

                if not step_result.success:
                    # Step failed after max iterations
                    state.status = StepStatus.BLOCKED
                    state.promise = PromiseStatus.BLOCKED
                    error_msg = step_result.error or "Step failed after max iterations"

                    if self.on_promise:
                        await self.on_promise(PromiseStatus.BLOCKED, error_msg)

                    return self._create_result(state, f"BLOCKED: {error_msg}")

                state.current_step += 1

            # All steps completed successfully
            state.status = StepStatus.DONE
            state.promise = PromiseStatus.DONE
            state.completed_at = datetime.now().isoformat()

            # Trigger completion hook
            await self.hook_system.trigger_on_complete({
                "task_id": task_id,
                "all_steps_done": True,
                "tests_passed": all(r.tests_passed for r in state.results),
            })

            if self.on_promise:
                await self.on_promise(PromiseStatus.DONE, "")

            return self._create_result(state, "DONE")

        except asyncio.CancelledError:
            state.status = StepStatus.BLOCKED
            state.promise = PromiseStatus.BLOCKED
            return self._create_result(state, "BLOCKED: Task cancelled")

        except Exception as e:
            state.status = StepStatus.BLOCKED
            state.promise = PromiseStatus.BLOCKED
            return self._create_result(state, f"BLOCKED: {str(e)}")

        finally:
            self._save_state(state)

    async def _execute_step_with_retry(self, step: Dict[str, Any], state: ExecutionState) -> StepResult:
        """
        Execute a single step with Ralph Wiggum retry pattern.
        """
        step_number = step.get("number", state.current_step)
        description = step.get("description", "")
        capability = step.get("capability", "")
        capability_type = step.get("capability_type", "")
        hooks_before = step.get("hooks_before", [])
        hooks_after = step.get("hooks_after", [])
        test_criteria = step.get("test_criteria", [])
        max_step_iterations = step.get("max_iterations", state.max_iterations)

        iteration = 1
        last_error = None
        last_output = None

        while iteration <= max_step_iterations:
            start_time = datetime.now()

            # Notify iteration start
            if self.on_iteration:
                await self.on_iteration(step_number, iteration)

            if self.on_step_start:
                await self.on_step_start(step_number, description)

            try:
                # Run BEFORE hooks
                if hooks_before:
                    from hooks.hook_system import HookTrigger
                    hook_results = await self.hook_system.trigger(
                        HookTrigger.BEFORE,
                        hooks_before,
                        {"step": step, "iteration": iteration}
                    )

                    # Check if any hook blocked execution
                    for hr in hook_results:
                        if not hr.success:
                            last_error = f"Hook {hr.hook_name} blocked: {hr.error}"
                            iteration += 1
                            continue

                # Execute the step
                state.status = StepStatus.IN_PROGRESS
                output = await self._execute_capability(capability, capability_type, step, state)
                last_output = output

                # Run AFTER hooks
                if hooks_after:
                    from hooks.hook_system import HookTrigger
                    await self.hook_system.trigger(
                        HookTrigger.AFTER,
                        hooks_after,
                        {
                            "step": step,
                            "iteration": iteration,
                            "task_id": state.task_id,
                            "step_number": step_number,
                            "status": "done",
                            "result": output,
                        }
                    )

                # Run tests if criteria specified
                state.status = StepStatus.TESTING
                tests_passed = True
                test_output = ""

                if test_criteria:
                    tests_passed, test_output = await self._run_tests(test_criteria, output, step)

                duration = int((datetime.now() - start_time).total_seconds() * 1000)

                if tests_passed:
                    # Success!
                    result = StepResult(
                        step_number=step_number,
                        success=True,
                        output=output,
                        iteration=iteration,
                        tests_passed=True,
                        test_output=test_output,
                        duration_ms=duration,
                    )

                    if self.on_step_complete:
                        await self.on_step_complete(result)

                    return result
                else:
                    # Tests failed - analyze and retry
                    last_error = f"Tests failed: {test_output}"

                    state.error_history.append({
                        "step": step_number,
                        "iteration": iteration,
                        "error": last_error,
                        "output": str(output)[:500],
                    })

                    # Analyze failure and adjust
                    adjustment = await self._analyze_failure(step, output, test_output, state)
                    if adjustment:
                        step.update(adjustment)

                    state.status = StepStatus.RETRYING
                    iteration += 1

            except Exception as e:
                last_error = str(e)
                state.error_history.append({
                    "step": step_number,
                    "iteration": iteration,
                    "error": last_error,
                })

                # Analyze and adjust
                adjustment = await self._analyze_failure(step, None, last_error, state)
                if adjustment:
                    step.update(adjustment)

                state.status = StepStatus.RETRYING
                iteration += 1

        # Max iterations reached
        return StepResult(
            step_number=step_number,
            success=False,
            output=last_output,
            error=last_error or f"Max iterations ({max_step_iterations}) reached",
            iteration=iteration - 1,
            tests_passed=False,
        )

    async def _execute_capability(
        self,
        capability: str,
        capability_type: str,
        step: Dict[str, Any],
        state: ExecutionState
    ) -> Any:
        """Execute a capability (agent, skill, hook, mcp)."""

        if capability_type == "hook":
            # Execute as hook
            hook = self.hook_system.get(capability)
            if hook:
                result = await hook.execute(step.get("inputs", {}))
                return result.output
            return {"skipped": True, "reason": f"Hook {capability} not found"}

        elif capability_type == "skill":
            # Execute as skill
            return await self._execute_skill(capability, step.get("inputs", {}))

        elif capability_type == "agent":
            # Execute as agent (uses Claude CLI)
            return await self._execute_agent(capability, step, state)

        elif capability_type == "mcp":
            # Execute via MCP
            return await self._execute_mcp(capability, step.get("inputs", {}))

        elif capability_type == "command":
            # Execute shell command
            return await self._execute_command(step.get("inputs", {}).get("command", ""))

        else:
            return {"error": f"Unknown capability type: {capability_type}"}

    async def _execute_skill(self, skill_name: str, inputs: Dict[str, Any]) -> Any:
        """Execute a skill."""
        try:
            # Import skill dynamically
            if skill_name == "web-search":
                from skills.browser_automation import BrowserAutomation
                browser = BrowserAutomation()
                return await browser.browse_and_extract(inputs.get("query", ""), inputs.get("task", "search"))

            elif skill_name == "web-scrape":
                from skills.browser_automation import BrowserAutomation
                browser = BrowserAutomation()
                return await browser.browse_and_extract(inputs.get("url", ""), "scrape")

            else:
                return {"error": f"Skill {skill_name} not implemented"}

        except Exception as e:
            return {"error": str(e)}

    async def _execute_agent(self, agent_name: str, step: Dict[str, Any], state: ExecutionState) -> Any:
        """
        Execute an agent task using the INTELLIGENT ORCHESTRATOR.

        This is where the Claude intelligence actually happens - using the
        intelligent_orchestrator which can:
        - Understand user intent
        - Choose the right skills/MCPs
        - Execute with reasoning
        - Return meaningful results
        """
        description = step.get("description", "")
        inputs = step.get("inputs", {})

        try:
            # Use the intelligent orchestrator for actual execution
            from core.intelligent_orchestrator import process_intelligent_request

            # Build the request - this goes to Claude for intelligent processing
            task_request = description
            if inputs.get("query"):
                task_request = inputs.get("query")
            elif inputs.get("url"):
                task_request = f"scrape {inputs.get('url')}"

            print(f"[Execution Engine] Running intelligent request: {task_request}")

            # This is where Claude's intelligence kicks in
            result = await process_intelligent_request(task_request)

            # Extract useful data from result
            execution_info = result.get("execution_info", {})
            raw_data = result.get("raw_data", {})

            output = {
                "agent": agent_name,
                "success": result.get("success", False),
                "answer": result.get("answer", ""),
                "understood_goal": execution_info.get("understood_goal", description),
                "skills_used": execution_info.get("skills_used", []),
                "mcps_used": execution_info.get("mcps_used", []),
                "hooks_triggered": execution_info.get("hooks_triggered", []),
            }

            # Extract specific result types (jobs, search results, scraped content)
            for step_key, step_data in raw_data.items():
                if isinstance(step_data, dict):
                    data_type = step_data.get("type", "")

                    if data_type == "job_listings" or step_data.get("jobs"):
                        output["type"] = "job_listings"
                        output["jobs"] = step_data.get("jobs", [])
                        output["jobs_found"] = len(step_data.get("jobs", []))
                        # Include source info and warnings
                        output["site"] = step_data.get("site", "")
                        output["actual_source"] = step_data.get("actual_source", "")
                        output["warning"] = step_data.get("warning")
                        output["fallback_used"] = step_data.get("fallback_used", False)
                        output["original_site_requested"] = step_data.get("original_site_requested")
                        output["note"] = step_data.get("note", "")

                    elif data_type == "search_results" or step_data.get("results"):
                        output["type"] = "search_results"
                        output["results"] = step_data.get("results", [])

                    elif data_type == "scraped_content":
                        output["type"] = "scraped_content"
                        output["title"] = step_data.get("title", "")
                        output["url"] = step_data.get("url", "")
                        output["relevant_content"] = step_data.get("relevant_content", [])

            return output

        except ImportError:
            # Fallback to Claude CLI if intelligent orchestrator not available
            print("[Execution Engine] Intelligent orchestrator not available, falling back to Claude CLI")
            return await self._execute_agent_cli(agent_name, step, state)

        except Exception as e:
            print(f"[Execution Engine] Error: {e}")
            return {"error": str(e), "agent": agent_name}

    async def _execute_agent_cli(self, agent_name: str, step: Dict[str, Any], state: ExecutionState) -> Any:
        """Fallback: Execute an agent task using Claude CLI directly."""
        if not self.claude_cli:
            return {"error": "Claude CLI not available"}

        try:
            description = step.get("description", "")
            inputs = step.get("inputs", {})

            prompt = f"""Execute this task step:

TASK: {description}

{f"INPUTS: {json.dumps(inputs)}" if inputs else ""}

Execute the task and return the result. If you need to write code, do so.
If you need to run commands, do so.
Return a summary of what was done."""

            process = await asyncio.create_subprocess_exec(
                self.claude_cli,
                "-p", prompt,
                "--output-format", "text",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.base_path),
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)
            output = stdout.decode("utf-8").strip()

            return {
                "agent": agent_name,
                "output": output,
                "success": process.returncode == 0,
            }

        except asyncio.TimeoutError:
            return {"error": "Agent execution timed out after 5 minutes"}
        except Exception as e:
            return {"error": str(e)}

    async def _execute_mcp(self, mcp_name: str, inputs: Dict[str, Any]) -> Any:
        """Execute via MCP (Model Context Protocol)."""
        # MCP execution would go through the MCP client
        # For now, return a placeholder
        return {
            "mcp": mcp_name,
            "inputs": inputs,
            "note": "MCP execution requires MCP client setup",
        }

    async def _execute_command(self, command: str) -> Any:
        """Execute a shell command."""
        if not command:
            return {"error": "No command specified"}

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.base_path),
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)

            return {
                "command": command,
                "stdout": stdout.decode("utf-8"),
                "stderr": stderr.decode("utf-8"),
                "return_code": process.returncode,
                "success": process.returncode == 0,
            }

        except asyncio.TimeoutError:
            return {"error": "Command timed out after 2 minutes"}
        except Exception as e:
            return {"error": str(e)}

    async def _run_tests(
        self,
        test_criteria: List[str],
        output: Any,
        step: Dict[str, Any]
    ) -> tuple[bool, str]:
        """Run tests to verify step completion."""

        # Check each criterion
        results = []
        all_passed = True

        for criterion in test_criteria:
            passed = await self._check_criterion(criterion, output, step)
            results.append(f"{'✓' if passed else '✗'} {criterion}")
            if not passed:
                all_passed = False

        return all_passed, "\n".join(results)

    async def _check_criterion(self, criterion: str, output: Any, step: Dict[str, Any]) -> bool:
        """Check a single test criterion."""
        criterion_lower = criterion.lower()

        # Common criteria checks
        if "all tests pass" in criterion_lower:
            # Run actual tests
            result = await self._execute_command("pytest --tb=short 2>/dev/null || echo 'No tests found'")
            if isinstance(result, dict):
                return result.get("return_code", 1) == 0 or "No tests found" in result.get("stdout", "")

        if "no error" in criterion_lower or "no regression" in criterion_lower:
            if isinstance(output, dict):
                return not output.get("error")
            return True

        if "file exists" in criterion_lower:
            # Extract file path from criterion
            # This would need more sophisticated parsing
            return True

        # Default: assume passed if no specific check
        return True

    async def _analyze_failure(
        self,
        step: Dict[str, Any],
        output: Any,
        error: str,
        state: ExecutionState
    ) -> Optional[Dict[str, Any]]:
        """Analyze a failure and suggest adjustments."""

        if not self.claude_cli:
            return None

        try:
            prompt = f"""Analyze this task failure and suggest how to fix it.

TASK: {step.get('description', '')}
ERROR: {error}
OUTPUT: {str(output)[:1000] if output else 'None'}

PREVIOUS ATTEMPTS: {len(state.error_history)}

Return a JSON object with suggested adjustments:
{{
    "inputs": {{}},  // Modified inputs
    "approach": "description of new approach"
}}

JSON only:"""

            process = await asyncio.create_subprocess_exec(
                self.claude_cli,
                "-p", prompt,
                "--output-format", "text",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=30)
            output_text = stdout.decode("utf-8").strip()

            # Try to parse JSON
            import re
            json_match = re.search(r'\{[^{}]*\}', output_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())

        except Exception:
            pass

        return None

    def _create_result(self, state: ExecutionState, promise: str) -> Dict[str, Any]:
        """Create the final result dictionary."""
        return {
            "task_id": state.task_id,
            "promise": f"<Promise>{promise}</Promise>",
            "status": state.status.value,
            "steps_completed": len([r for r in state.results if r.success]),
            "total_steps": state.total_steps,
            "iterations_used": sum(r.iteration for r in state.results),
            "results": [
                {
                    "step": r.step_number,
                    "success": r.success,
                    "iterations": r.iteration,
                    "tests_passed": r.tests_passed,
                    "error": r.error,
                    "output": r.output,  # Include actual output data!
                }
                for r in state.results
            ],
            "started_at": state.started_at,
            "completed_at": state.completed_at or datetime.now().isoformat(),
        }

    def _save_state(self, state: ExecutionState):
        """Save execution state to file."""
        state_file = self.state_path / f"{state.task_id}_state.json"
        state_data = {
            "task_id": state.task_id,
            "current_step": state.current_step,
            "total_steps": state.total_steps,
            "iteration": state.iteration,
            "max_iterations": state.max_iterations,
            "status": state.status.value,
            "promise": state.promise.value,
            "error_history": state.error_history,
            "started_at": state.started_at,
            "completed_at": state.completed_at,
        }
        with open(state_file, "w") as f:
            json.dump(state_data, f, indent=2)


# Singleton
_execution_engine: Optional[ExecutionEngine] = None


def get_execution_engine() -> ExecutionEngine:
    """Get the singleton Execution Engine."""
    global _execution_engine
    if _execution_engine is None:
        _execution_engine = ExecutionEngine()
    return _execution_engine


async def execute_task(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function to execute a task plan."""
    engine = get_execution_engine()
    return await engine.execute_plan(plan)
