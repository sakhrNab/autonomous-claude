"""
Planning Agent

The Planning Agent is responsible for:
1. Analyzing incoming tasks
2. Understanding what the user really wants
3. Creating detailed execution plans
4. Updating TODO.md
5. Asking clarifying questions when needed
6. Determining which agents/skills/hooks to use

This agent ALWAYS runs first before any task execution.
"""

import os
import json
import asyncio
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class ExecutionStep:
    """A single step in the execution plan."""
    number: int
    description: str
    capability: str  # agent, skill, or hook to use
    capability_type: str  # "agent", "skill", "hook", "mcp"
    inputs: Dict[str, Any] = field(default_factory=dict)
    expected_output: str = ""
    test_criteria: List[str] = field(default_factory=list)
    hooks_before: List[str] = field(default_factory=list)
    hooks_after: List[str] = field(default_factory=list)
    max_iterations: int = 10
    status: str = "pending"  # pending, in_progress, testing, done, blocked


@dataclass
class ExecutionPlan:
    """Complete execution plan for a task."""
    task_id: str
    original_request: str
    understood_goal: str
    category: str
    steps: List[ExecutionStep]
    clarifying_questions: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    requires_web_search: bool = False
    requires_db_check: bool = False
    requires_ui: bool = False
    estimated_complexity: str = "medium"  # simple, medium, complex
    created_at: str = ""
    completion_promise: str = "DONE"


class PlanningAgent:
    """
    The Planning Agent - analyzes tasks and creates execution plans.

    This is the FIRST agent that runs for any task.
    """

    def __init__(self):
        self.base_path = Path(__file__).parent.parent
        self.todo_path = self.base_path / "TODO.md"
        self.plans_path = self.base_path / "plans"
        self.plans_path.mkdir(parents=True, exist_ok=True)

        # Claude CLI for intelligent analysis
        self.claude_cli = shutil.which("claude")

    async def analyze_and_plan(self, task_request: str, context: Optional[Dict] = None) -> ExecutionPlan:
        """
        Analyze a task request and create an execution plan.

        This is the main entry point.
        """
        from core.source_of_truth import get_source_of_truth

        # Get routing from Source of Truth
        sot = get_source_of_truth()
        routing = sot.route_task(task_request)

        # Analyze the task more deeply
        analysis = await self._deep_analyze(task_request, routing, context)

        # Check if we need to ask questions
        questions = self._identify_questions(task_request, analysis)

        # Create the execution plan
        plan = self._create_plan(task_request, analysis, routing, questions)

        # Save the plan
        self._save_plan(plan)

        # Update TODO.md
        await self._update_todo(plan)

        return plan

    async def _deep_analyze(self, task: str, routing: Dict, context: Optional[Dict]) -> Dict:
        """
        Perform deep analysis of the task using Claude if available.
        """
        analysis = {
            "task": task,
            "routing": routing,
            "understood_goal": task,  # Default
            "complexity": "medium",
            "requires_ui": False,
            "requires_api": False,
            "requires_db": routing.get("check_db_first", False),
            "requires_testing": routing.get("requires_testing", True),
            "suggested_steps": [],
        }

        # Check for UI requirements
        ui_keywords = ["ui", "page", "component", "frontend", "design", "responsive", "button", "form"]
        analysis["requires_ui"] = any(kw in task.lower() for kw in ui_keywords)

        # Check for API requirements
        api_keywords = ["api", "endpoint", "rest", "graphql", "webhook"]
        analysis["requires_api"] = any(kw in task.lower() for kw in api_keywords)

        # Determine complexity
        if any(word in task.lower() for word in ["simple", "basic", "quick", "small"]):
            analysis["complexity"] = "simple"
        elif any(word in task.lower() for word in ["complex", "full", "complete", "entire", "comprehensive"]):
            analysis["complexity"] = "complex"

        # Use Claude for deeper understanding if available
        if self.claude_cli:
            deeper = await self._ask_claude_for_analysis(task, context)
            if deeper:
                analysis.update(deeper)

        return analysis

    async def _ask_claude_for_analysis(self, task: str, context: Optional[Dict]) -> Optional[Dict]:
        """Use Claude CLI to analyze the task more deeply."""
        try:
            prompt = f"""Analyze this task request and return a JSON object with your analysis.

TASK: {task}

{f"CONTEXT: {json.dumps(context)}" if context else ""}

Return ONLY a JSON object with these fields:
{{
    "understood_goal": "What the user actually wants (clear, specific)",
    "complexity": "simple|medium|complex",
    "suggested_steps": ["Step 1", "Step 2", ...],
    "requires_web_search": true/false,
    "questions_to_ask": ["Question 1", ...] (only if truly ambiguous)
}}

JSON only, no markdown, no explanation:"""

            process = await asyncio.create_subprocess_exec(
                self.claude_cli,
                "-p", prompt,
                "--output-format", "text",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=30)
            output = stdout.decode("utf-8").strip()

            # Try to parse JSON
            # Find JSON in output
            import re
            json_match = re.search(r'\{[^{}]*\}', output, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())

        except Exception as e:
            print(f"Claude analysis error: {e}")

        return None

    def _identify_questions(self, task: str, analysis: Dict) -> List[str]:
        """Identify clarifying questions that should be asked."""
        questions = analysis.get("questions_to_ask", [])

        # Add standard questions for ambiguous cases
        if analysis.get("complexity") == "complex" and not questions:
            task_lower = task.lower()

            # Database questions
            if analysis.get("requires_db"):
                if "which database" not in task_lower and "postgres" not in task_lower:
                    questions.append("Which database should be used? (PostgreSQL recommended)")

            # UI questions
            if analysis.get("requires_ui"):
                if "design" not in task_lower and "style" not in task_lower:
                    questions.append("Should the UI follow a specific design system?")

        return questions

    def _create_plan(self, task: str, analysis: Dict, routing: Dict, questions: List[str]) -> ExecutionPlan:
        """Create the execution plan."""
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        steps = []

        # Step 1: Always start with context loading if complex
        if analysis.get("complexity") != "simple":
            steps.append(ExecutionStep(
                number=1,
                description="Load project context and understand existing code",
                capability="load-context",
                capability_type="hook",
                expected_output="Project context loaded",
                status="pending",
            ))

        # Step 2: Web search if needed
        if routing.get("search_web_first") or analysis.get("requires_web_search"):
            steps.append(ExecutionStep(
                number=len(steps) + 1,
                description="Search web for latest information and best practices",
                capability="web-search",
                capability_type="skill",
                inputs={"query": task},
                expected_output="Relevant search results",
                status="pending",
            ))

        # Step 3: DB check if needed
        if routing.get("check_db_first"):
            steps.append(ExecutionStep(
                number=len(steps) + 1,
                description="Check database for existing data/schema",
                capability="postgresql-mcp",
                capability_type="mcp",
                expected_output="Database state understood",
                status="pending",
            ))

        # Step 4: Main execution steps from analysis
        suggested_steps = analysis.get("suggested_steps", [])
        if suggested_steps:
            for step_desc in suggested_steps:
                steps.append(ExecutionStep(
                    number=len(steps) + 1,
                    description=step_desc,
                    capability=routing.get("primary_capability", "code-agent"),
                    capability_type="agent",
                    expected_output=f"Completed: {step_desc}",
                    hooks_after=["update-todo"],
                    status="pending",
                ))
        else:
            # Default main step
            steps.append(ExecutionStep(
                number=len(steps) + 1,
                description=f"Execute: {analysis.get('understood_goal', task)}",
                capability=routing.get("primary_capability", "code-agent"),
                capability_type="agent",
                expected_output="Task completed",
                hooks_after=["update-todo"],
                status="pending",
            ))

        # Step N-1: Testing (only for code/implementation tasks, NOT for scraping/search)
        task_lower = task.lower()
        is_scrape_or_search = any(kw in task_lower for kw in ['scrape', 'search', 'find', 'headlines', 'news', 'extract', 'fetch'])
        if routing.get("requires_testing", False) and not is_scrape_or_search:
            steps.append(ExecutionStep(
                number=len(steps) + 1,
                description="Run tests to verify implementation",
                capability="testing-agent",
                capability_type="agent",
                test_criteria=["All tests pass", "No regressions"],
                expected_output="All tests passing",
                status="pending",
            ))

        # Step N: Completion
        steps.append(ExecutionStep(
            number=len(steps) + 1,
            description="Verify completion and output promise",
            capability="check-completion",
            capability_type="hook",
            expected_output="<Promise>DONE</Promise>",
            status="pending",
        ))

        return ExecutionPlan(
            task_id=task_id,
            original_request=task,
            understood_goal=analysis.get("understood_goal", task),
            category=routing.get("category", "unknown"),
            steps=steps,
            clarifying_questions=questions,
            dependencies=routing.get("dependencies", []),
            requires_web_search=routing.get("search_web_first", False),
            requires_db_check=routing.get("check_db_first", False),
            requires_ui=analysis.get("requires_ui", False),
            estimated_complexity=analysis.get("complexity", "medium"),
            created_at=datetime.now().isoformat(),
        )

    def _save_plan(self, plan: ExecutionPlan):
        """Save the plan to a file."""
        plan_file = self.plans_path / f"{plan.task_id}.json"
        plan_data = asdict(plan)
        with open(plan_file, "w") as f:
            json.dump(plan_data, f, indent=2)

    async def _update_todo(self, plan: ExecutionPlan):
        """Update TODO.md with the new plan."""
        todo_content = self._generate_todo_content(plan)

        # Read existing TODO if it exists
        existing_content = ""
        if self.todo_path.exists():
            existing_content = self.todo_path.read_text()

        # Append new task
        new_content = existing_content + "\n\n" + todo_content
        self.todo_path.write_text(new_content)

    def _generate_todo_content(self, plan: ExecutionPlan) -> str:
        """Generate TODO.md content for a plan."""
        lines = [
            f"## Task: {plan.task_id}",
            f"**Request:** {plan.original_request}",
            f"**Goal:** {plan.understood_goal}",
            f"**Category:** {plan.category}",
            f"**Complexity:** {plan.estimated_complexity}",
            f"**Created:** {plan.created_at}",
            "",
            "### Steps:",
        ]

        for step in plan.steps:
            status_icon = {
                "pending": "[ ]",
                "in_progress": "[~]",
                "testing": "[T]",
                "done": "[x]",
                "blocked": "[!]",
            }.get(step.status, "[ ]")

            lines.append(f"{step.number}. {status_icon} {step.description}")
            lines.append(f"   - Capability: `{step.capability}` ({step.capability_type})")
            if step.test_criteria:
                lines.append(f"   - Tests: {', '.join(step.test_criteria)}")

        lines.extend([
            "",
            "### Status: PENDING",
            "",
            "### Completion:",
            "```",
            "<Promise>PENDING</Promise>",
            "```",
            "",
            "---",
        ])

        return "\n".join(lines)

    async def update_step_status(self, task_id: str, step_number: int, status: str, result: Optional[str] = None):
        """Update a specific step's status in the plan and TODO."""
        plan_file = self.plans_path / f"{task_id}.json"
        if not plan_file.exists():
            return

        with open(plan_file) as f:
            plan_data = json.load(f)

        # Update step
        for step in plan_data["steps"]:
            if step["number"] == step_number:
                step["status"] = status
                break

        # Save updated plan
        with open(plan_file, "w") as f:
            json.dump(plan_data, f, indent=2)

        # Update TODO.md
        await self._refresh_todo()

    async def mark_task_complete(self, task_id: str, success: bool = True, message: str = ""):
        """Mark a task as complete with the completion promise."""
        plan_file = self.plans_path / f"{task_id}.json"
        if not plan_file.exists():
            return

        # Update TODO.md with completion promise
        if self.todo_path.exists():
            content = self.todo_path.read_text()

            # Find and update the task section
            if task_id in content:
                if success:
                    content = content.replace(
                        f"<Promise>PENDING</Promise>",
                        f"<Promise>DONE</Promise>"
                    )
                    content = content.replace(
                        "### Status: PENDING",
                        "### Status: DONE"
                    )
                else:
                    content = content.replace(
                        f"<Promise>PENDING</Promise>",
                        f"<Promise>BLOCKED: {message}</Promise>"
                    )
                    content = content.replace(
                        "### Status: PENDING",
                        f"### Status: BLOCKED - {message}"
                    )

                self.todo_path.write_text(content)

    async def _refresh_todo(self):
        """Refresh TODO.md from all plans."""
        # This would regenerate TODO.md from all plan files
        # For now, we just keep it updated incrementally
        pass

    def get_plan(self, task_id: str) -> Optional[ExecutionPlan]:
        """Load a plan by ID."""
        plan_file = self.plans_path / f"{task_id}.json"
        if not plan_file.exists():
            return None

        with open(plan_file) as f:
            data = json.load(f)

        # Convert steps
        steps = [ExecutionStep(**s) for s in data.pop("steps")]
        return ExecutionPlan(**data, steps=steps)


# Singleton
_planning_agent: Optional[PlanningAgent] = None


def get_planning_agent() -> PlanningAgent:
    """Get the singleton Planning Agent."""
    global _planning_agent
    if _planning_agent is None:
        _planning_agent = PlanningAgent()
    return _planning_agent


async def plan_task(task_request: str, context: Optional[Dict] = None) -> ExecutionPlan:
    """Convenience function to plan a task."""
    agent = get_planning_agent()
    return await agent.analyze_and_plan(task_request, context)
