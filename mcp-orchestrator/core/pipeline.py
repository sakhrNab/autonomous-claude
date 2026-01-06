"""
Pipeline Orchestrator - The Core Brain

Implements the flow:
User Request → Source of Truth → Agent Router → Skills → Hooks → Result

This is the main entry point for all task execution.
"""

import os
import json
import asyncio
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class AgentType(Enum):
    PLANNING = "planning"
    CODE = "code"
    API = "api"
    DB = "db"
    TEST = "test"
    CACHE = "cache"
    AI = "ai"
    SEARCH = "search"
    SCRAPE = "scrape"
    UI = "ui"


@dataclass
class AgentConfig:
    """Configuration for an agent."""
    name: str
    description: str
    priority: int
    tools: List[str]
    skills: List[str] = field(default_factory=list)
    mcp: Optional[str] = None
    can_delegate_to: List[str] = field(default_factory=list)
    hooks_after: List[str] = field(default_factory=list)


@dataclass
class ExecutionStep:
    """A single step in the execution pipeline."""
    agent: str
    task: str
    skills: List[str] = field(default_factory=list)
    depends_on: List[int] = field(default_factory=list)
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[Dict] = None


@dataclass
class ExecutionPlan:
    """Complete execution plan for a request."""
    id: str
    original_request: str
    understood_goal: str
    complexity: str
    agents_needed: List[str]
    skills_needed: List[str]
    mcps_needed: List[str]
    hooks_to_trigger: List[str]
    steps: List[ExecutionStep]
    batch_test_after: int = 10
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class PipelineOrchestrator:
    """
    The main orchestration pipeline.

    Flow:
    1. User submits request
    2. Source of Truth analyzes and routes
    3. Planning agent creates execution plan
    4. Agents execute with skills
    5. Hooks validate at each step
    6. Test agent runs after batches
    7. Results returned
    """

    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.agents_path = self.project_root / ".claude" / "agents"
        self.skills_path = self.project_root / ".claude" / "skills"
        self.hooks_path = self.project_root / ".claude" / "hooks"

        self.claude_cli = shutil.which("claude")
        self.agents: Dict[str, AgentConfig] = {}
        self.task_counter = 0
        self.completed_since_test = 0

        self._load_agents()
        self._load_hooks()

    def _load_agents(self):
        """Load agent configurations from .claude/agents/"""
        if not self.agents_path.exists():
            return

        for agent_file in self.agents_path.glob("*.md"):
            try:
                content = agent_file.read_text()
                # Parse YAML frontmatter
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        import yaml
                        frontmatter = yaml.safe_load(parts[1])

                        self.agents[frontmatter["name"]] = AgentConfig(
                            name=frontmatter["name"],
                            description=frontmatter.get("description", ""),
                            priority=frontmatter.get("priority", 50),
                            tools=frontmatter.get("tools", "").split(", ") if frontmatter.get("tools") else [],
                            skills=frontmatter.get("skills", "").split(", ") if frontmatter.get("skills") else [],
                            mcp=frontmatter.get("mcp"),
                        )
            except Exception as e:
                print(f"[Pipeline] Error loading agent {agent_file.name}: {e}")

    def _load_hooks(self):
        """Load hook configurations."""
        self.hooks = {}
        hooks_file = self.hooks_path / "hooks.json"
        if hooks_file.exists():
            try:
                self.hooks = json.loads(hooks_file.read_text())
            except Exception as e:
                print(f"[Pipeline] Error loading hooks: {e}")

    async def process_request(self, user_request: str, context: Dict = None) -> Dict[str, Any]:
        """
        Main entry point - process a user request through the pipeline.

        Args:
            user_request: The user's natural language request
            context: Optional context (project info, previous results, etc.)

        Returns:
            Execution result with answer, data, and metadata
        """
        context = context or {}

        print(f"[Pipeline] Processing: {user_request[:100]}...")

        # Step 1: Route through Source of Truth
        routing = await self._route_request(user_request)

        # Step 2: Create execution plan
        plan = await self._create_plan(user_request, routing, context)

        # Step 3: Execute the plan
        result = await self._execute_plan(plan)

        # Step 4: Check if batch testing needed
        self.completed_since_test += 1
        if self.completed_since_test >= plan.batch_test_after:
            await self._run_batch_tests()
            self.completed_since_test = 0

        # Step 5: Trigger post-execution hooks
        await self._trigger_hooks("PostExecution", result)

        return result

    async def _route_request(self, request: str) -> Dict[str, Any]:
        """Route request through Source of Truth."""
        from core.source_of_truth import get_source_of_truth

        sot = get_source_of_truth()
        return sot.route_task(request)

    async def _create_plan(
        self,
        request: str,
        routing: Dict,
        context: Dict
    ) -> ExecutionPlan:
        """Create an execution plan using the planning agent."""

        plan_id = f"plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Determine which agents are needed based on routing
        agents_needed = self._determine_agents(request, routing)
        skills_needed = self._determine_skills(request, routing, agents_needed)
        mcps_needed = routing.get("mcps", [])

        # Build execution steps
        steps = self._build_execution_steps(request, agents_needed, skills_needed)

        # Determine hooks to trigger
        hooks = self._determine_hooks(agents_needed)

        # Complexity assessment
        complexity = "simple"
        if len(agents_needed) > 2:
            complexity = "complex"
        elif len(agents_needed) > 1:
            complexity = "medium"

        return ExecutionPlan(
            id=plan_id,
            original_request=request,
            understood_goal=routing.get("understood_goal", request),
            complexity=complexity,
            agents_needed=agents_needed,
            skills_needed=skills_needed,
            mcps_needed=mcps_needed,
            hooks_to_trigger=hooks,
            steps=steps,
            batch_test_after=10,
        )

    def _determine_agents(self, request: str, routing: Dict) -> List[str]:
        """Determine which agents are needed for the request."""
        request_lower = request.lower()
        agents = []

        # Always start with planning for complex requests
        if routing.get("category") in ["code", "api", "database", "ui"]:
            agents.append("planning-agent")

        # Map intent to agents
        if any(kw in request_lower for kw in ["scrape", "extract", "headlines", "content from"]):
            agents.append("scrape-agent")

        if any(kw in request_lower for kw in ["search", "find", "look up", "latest"]):
            agents.append("search-agent")

        if any(kw in request_lower for kw in ["code", "implement", "create", "build", "fix"]):
            agents.append("code-agent")

        if any(kw in request_lower for kw in ["api", "endpoint", "rest", "graphql"]):
            agents.append("api-agent")

        if any(kw in request_lower for kw in ["database", "db", "sql", "schema", "migration"]):
            agents.append("db-agent")

        if any(kw in request_lower for kw in ["test", "verify", "check"]):
            agents.append("test-agent")

        if any(kw in request_lower for kw in ["ui", "frontend", "page", "component"]):
            agents.append("ui-agent")

        # Always consider caching for data operations
        if any(kw in request_lower for kw in ["api", "database", "fetch", "load"]):
            agents.append("cache-agent")

        # Consider AI utilization for complex tasks
        if routing.get("category") in ["code", "analysis"]:
            agents.append("ai-agent")

        return agents if agents else ["planning-agent"]

    def _determine_skills(
        self,
        request: str,
        routing: Dict,
        agents: List[str]
    ) -> List[str]:
        """Determine which skills are needed."""
        skills = []

        if "scrape-agent" in agents:
            skills.extend(["web-scrape", "data-extraction"])

        if "search-agent" in agents:
            skills.append("web-search")

        if "api-agent" in agents:
            skills.extend(["api-design", "openapi-spec"])

        if "db-agent" in agents:
            skills.extend(["sql-optimization", "schema-design"])

        if "code-agent" in agents:
            skills.extend(["code-review", "security-check"])

        return list(set(skills))

    def _build_execution_steps(
        self,
        request: str,
        agents: List[str],
        skills: List[str]
    ) -> List[ExecutionStep]:
        """Build the sequence of execution steps."""
        steps = []
        step_num = 0

        for agent in agents:
            # Determine skills for this agent
            agent_skills = []
            if agent == "scrape-agent":
                agent_skills = [s for s in skills if "scrape" in s or "extraction" in s]
            elif agent == "search-agent":
                agent_skills = [s for s in skills if "search" in s]
            elif agent == "api-agent":
                agent_skills = [s for s in skills if "api" in s]

            step = ExecutionStep(
                agent=agent,
                task=request,
                skills=agent_skills,
                depends_on=[step_num - 1] if step_num > 0 else [],
            )
            steps.append(step)
            step_num += 1

        return steps

    def _determine_hooks(self, agents: List[str]) -> List[str]:
        """Determine which hooks should be triggered."""
        hooks = ["update-todo"]

        if "code-agent" in agents:
            hooks.extend(["check-design-patterns", "run-tests"])

        if "api-agent" in agents:
            hooks.extend(["check-db-connection", "validate-api-spec"])

        if "db-agent" in agents:
            hooks.extend(["backup-db", "verify-migration"])

        return list(set(hooks))

    async def _execute_plan(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """Execute the plan step by step."""
        print(f"[Pipeline] Executing plan {plan.id} with {len(plan.steps)} steps")

        results = []
        all_success = True

        for i, step in enumerate(plan.steps):
            step.status = "running"
            print(f"[Pipeline] Step {i+1}: {step.agent}")

            try:
                # Execute the step
                step_result = await self._execute_step(step, plan)
                step.result = step_result
                step.status = "completed" if step_result.get("success") else "failed"

                if not step_result.get("success"):
                    all_success = False

                results.append({
                    "step": i + 1,
                    "agent": step.agent,
                    "status": step.status,
                    "result": step_result,
                })

                # Trigger step hooks
                await self._trigger_hooks("PostStep", step_result)

            except Exception as e:
                step.status = "failed"
                step.result = {"error": str(e)}
                all_success = False
                results.append({
                    "step": i + 1,
                    "agent": step.agent,
                    "status": "failed",
                    "error": str(e),
                })

        # Build final result
        return {
            "success": all_success,
            "plan_id": plan.id,
            "goal": plan.understood_goal,
            "complexity": plan.complexity,
            "steps_executed": len(results),
            "results": results,
            "agents_used": plan.agents_needed,
            "skills_used": plan.skills_needed,
            "answer": self._build_answer(plan, results),
        }

    async def _execute_step(self, step: ExecutionStep, plan: ExecutionPlan) -> Dict[str, Any]:
        """Execute a single step using the appropriate agent."""
        agent_name = step.agent

        # Route to specific execution method based on agent
        if agent_name == "scrape-agent":
            return await self._execute_scrape(step.task)
        elif agent_name == "search-agent":
            return await self._execute_search(step.task)
        elif agent_name in ["code-agent", "api-agent", "db-agent"]:
            return await self._execute_claude(agent_name, step.task)
        else:
            # Default: use Claude Code CLI
            return await self._execute_claude(agent_name, step.task)

    async def _execute_scrape(self, task: str) -> Dict[str, Any]:
        """Execute scraping task."""
        from core.capability_resolver import resolve_and_execute
        return await resolve_and_execute(task, {})

    async def _execute_search(self, task: str) -> Dict[str, Any]:
        """Execute search task."""
        from core.capability_resolver import resolve_and_execute
        return await resolve_and_execute(f"search {task}", {"query": task})

    async def _execute_claude(self, agent: str, task: str) -> Dict[str, Any]:
        """Execute task using Claude Code CLI."""
        if not self.claude_cli:
            return {"success": False, "error": "Claude CLI not available"}

        try:
            # Load agent prompt if available
            agent_prompt = ""
            agent_file = self.agents_path / f"{agent}.md"
            if agent_file.exists():
                content = agent_file.read_text()
                if "---" in content:
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        agent_prompt = parts[2].strip()

            prompt = f"""{agent_prompt}

TASK: {task}

Execute this task and return results."""

            process = await asyncio.create_subprocess_exec(
                self.claude_cli,
                "-p", prompt[:6000],  # Truncate for Windows
                "--output-format", "text",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.project_root),
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
            output = stdout.decode("utf-8").strip()

            return {
                "success": process.returncode == 0,
                "output": output,
                "agent": agent,
            }
        except asyncio.TimeoutError:
            return {"success": False, "error": "Timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _trigger_hooks(self, event: str, data: Dict) -> None:
        """Trigger hooks for an event."""
        hooks_config = self.hooks.get("hooks", {}).get(event, [])
        for hook in hooks_config:
            try:
                command = hook.get("hooks", [{}])[0].get("command", "")
                if command:
                    process = await asyncio.create_subprocess_shell(
                        command,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    await asyncio.wait_for(process.communicate(), timeout=10)
            except Exception as e:
                print(f"[Pipeline] Hook error: {e}")

    async def _run_batch_tests(self) -> Dict[str, Any]:
        """Run batch tests after N tasks."""
        print("[Pipeline] Running batch tests...")
        return await self._execute_claude("test-agent", "Run all tests and report results")

    def _build_answer(self, plan: ExecutionPlan, results: List[Dict]) -> str:
        """Build a human-readable answer from results."""
        if not results:
            return "No results available"

        # Find the most relevant result
        for r in results:
            result_data = r.get("result", {})
            if result_data.get("success"):
                # Check for specific content types
                data = result_data.get("data", {})

                if data.get("type") == "search_results":
                    search_results = data.get("results", [])
                    if search_results:
                        answer = f"Found {len(search_results)} results:\n\n"
                        for i, sr in enumerate(search_results[:5], 1):
                            answer += f"{i}. {sr.get('title', 'No title')}\n   {sr.get('url', '')}\n\n"
                        return answer

                if data.get("type") == "scraped_content":
                    content = data.get("relevant_content", [])
                    if content:
                        answer = f"Found content:\n\n"
                        for item in content[:10]:
                            answer += f"• {item}\n"
                        return answer

                # Generic output
                if result_data.get("output"):
                    return result_data["output"][:2000]

        return "Task completed but no specific content to display"


# Singleton
_pipeline: Optional[PipelineOrchestrator] = None


def get_pipeline() -> PipelineOrchestrator:
    """Get the singleton pipeline orchestrator."""
    global _pipeline
    if _pipeline is None:
        _pipeline = PipelineOrchestrator()
    return _pipeline


async def process_request(user_request: str, context: Dict = None) -> Dict[str, Any]:
    """Convenience function to process a request through the pipeline."""
    pipeline = get_pipeline()
    return await pipeline.process_request(user_request, context)
