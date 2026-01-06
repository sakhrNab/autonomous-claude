"""
Execution Planner - Creates intelligent execution plans

This module creates REAL execution plans that specify:
- What agents to use
- What skills to invoke
- What MCPs to call
- Step-by-step execution order
- Fallback strategies

Plans are saved to plans/ folder for:
- Debugging and transparency
- Reuse of similar plans
- Learning from past executions
"""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from enum import Enum


class StepType(Enum):
    """Types of execution steps."""
    MCP_CALL = "mcp_call"           # Call an MCP tool
    SKILL_INVOKE = "skill_invoke"   # Invoke a skill
    AGENT_TASK = "agent_task"       # Delegate to an agent
    CLAUDE_REASON = "claude_reason" # Use Claude for reasoning
    HTTP_REQUEST = "http_request"   # Direct HTTP call
    CONDITIONAL = "conditional"     # Branch based on condition
    PARALLEL = "parallel"           # Run steps in parallel


@dataclass
class ExecutionStep:
    """A single step in an execution plan."""
    id: str
    type: StepType
    name: str
    description: str

    # What to execute
    mcp: Optional[str] = None           # MCP name if type is MCP_CALL
    skill: Optional[str] = None         # Skill name if type is SKILL_INVOKE
    agent: Optional[str] = None         # Agent name if type is AGENT_TASK
    tool: Optional[str] = None          # Specific tool to use

    # Parameters
    params: Dict[str, Any] = field(default_factory=dict)

    # Dependencies
    depends_on: List[str] = field(default_factory=list)  # Step IDs this depends on

    # Fallback
    fallback_step: Optional[str] = None  # Step ID to run if this fails

    # Timeout
    timeout_seconds: int = 60

    # Output handling
    output_key: Optional[str] = None  # Key to store output in context

    def to_dict(self) -> Dict:
        d = asdict(self)
        d['type'] = self.type.value
        return d


@dataclass
class ExecutionPlan:
    """A complete execution plan."""
    id: str
    intent: str
    created_at: str

    # Plan metadata
    complexity: str = "simple"  # simple, moderate, complex
    estimated_duration_seconds: int = 30

    # The steps
    steps: List[ExecutionStep] = field(default_factory=list)

    # MCPs, skills, agents involved
    mcps_used: List[str] = field(default_factory=list)
    skills_used: List[str] = field(default_factory=list)
    agents_used: List[str] = field(default_factory=list)

    # Execution context (variables passed between steps)
    initial_context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "intent": self.intent,
            "created_at": self.created_at,
            "complexity": self.complexity,
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "steps": [s.to_dict() for s in self.steps],
            "mcps_used": self.mcps_used,
            "skills_used": self.skills_used,
            "agents_used": self.agents_used,
            "initial_context": self.initial_context,
        }


class ExecutionPlanner:
    """
    Creates execution plans for tasks.

    This is the "brain" that figures out HOW to accomplish a task
    by creating a step-by-step plan with agents, skills, and MCPs.
    """

    def __init__(self):
        self.plans_dir = Path(__file__).parent.parent / "plans"
        self.plans_dir.mkdir(exist_ok=True)

        # Clean up old task dumps (not real plans)
        self._cleanup_old_dumps()

    def _cleanup_old_dumps(self):
        """Remove old task dumps that aren't real plans."""
        for f in self.plans_dir.glob("task_*.json"):
            try:
                with open(f) as fp:
                    data = json.load(fp)
                # Old dumps have 'raw_data' or 'result', real plans have 'steps'
                if 'steps' not in data and ('raw_data' in data or 'result' in data):
                    f.unlink()
            except:
                pass

    def create_plan(self, intent: str, context: Dict[str, Any] = None) -> ExecutionPlan:
        """
        Create an execution plan for the given intent.

        Analyzes the intent and creates a step-by-step plan.
        """
        context = context or {}
        intent_lower = intent.lower()

        plan_id = f"plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        plan = ExecutionPlan(
            id=plan_id,
            intent=intent,
            created_at=datetime.now().isoformat(),
            initial_context=context,
        )

        # Analyze intent and create appropriate steps
        if self._is_scraping_task(intent_lower):
            self._add_scraping_steps(plan, intent, context)
        elif self._is_search_task(intent_lower):
            self._add_search_steps(plan, intent, context)
        elif self._is_automation_task(intent_lower):
            self._add_automation_steps(plan, intent, context)
        elif self._is_database_task(intent_lower):
            self._add_database_steps(plan, intent, context)
        else:
            # Default: use Claude reasoning
            self._add_general_steps(plan, intent, context)

        # Calculate complexity
        plan.complexity = self._calculate_complexity(plan)
        plan.estimated_duration_seconds = len(plan.steps) * 15

        # Save the plan
        self._save_plan(plan)

        return plan

    def _is_scraping_task(self, intent: str) -> bool:
        keywords = ['scrape', 'extract', 'crawl', 'from', '.com', '.org', '.io', 'website', 'page']
        return any(kw in intent for kw in keywords)

    def _is_search_task(self, intent: str) -> bool:
        keywords = ['search', 'find', 'look up', 'what is', 'how to', 'where']
        return any(kw in intent for kw in keywords)

    def _is_automation_task(self, intent: str) -> bool:
        keywords = ['automate', 'workflow', 'schedule', 'every', 'recurring', 'n8n']
        return any(kw in intent for kw in keywords)

    def _is_database_task(self, intent: str) -> bool:
        keywords = ['database', 'sql', 'query', 'postgres', 'mysql', 'select', 'insert']
        return any(kw in intent for kw in keywords)

    def _add_scraping_steps(self, plan: ExecutionPlan, intent: str, context: Dict):
        """Add steps for a scraping task."""

        # Step 1: Try Firecrawl (best for blocked sites)
        plan.steps.append(ExecutionStep(
            id="step_1_firecrawl",
            type=StepType.MCP_CALL,
            name="Scrape with Firecrawl",
            description="Use Firecrawl to scrape the target URL (handles JS, bypasses blocks)",
            mcp="firecrawl",
            tool="scrape",
            params={"url": context.get("url", ""), "intent": intent},
            fallback_step="step_2_playwright",
            timeout_seconds=60,
            output_key="scraped_content",
        ))
        plan.mcps_used.append("firecrawl")

        # Step 2: Fallback to Playwright
        plan.steps.append(ExecutionStep(
            id="step_2_playwright",
            type=StepType.MCP_CALL,
            name="Scrape with Playwright",
            description="Use Playwright browser automation as fallback",
            mcp="playwright",
            tool="browser_navigate",
            params={"url": context.get("url", "")},
            fallback_step="step_3_http",
            timeout_seconds=45,
            output_key="scraped_content",
        ))
        plan.mcps_used.append("playwright")

        # Step 3: Fallback to direct HTTP
        plan.steps.append(ExecutionStep(
            id="step_3_http",
            type=StepType.HTTP_REQUEST,
            name="Direct HTTP fetch",
            description="Simple HTTP request as last resort",
            params={"url": context.get("url", "")},
            fallback_step="step_4_alternative",
            timeout_seconds=30,
            output_key="scraped_content",
        ))

        # Step 4: Try alternative sources (for jobs, etc.)
        plan.steps.append(ExecutionStep(
            id="step_4_alternative",
            type=StepType.SKILL_INVOKE,
            name="Try alternative sources",
            description="Use universal scraper to try alternative sources",
            skill="universal_scraper",
            params={"intent": intent},
            timeout_seconds=60,
            output_key="scraped_content",
        ))
        plan.skills_used.append("universal_scraper")

        # Step 5: Extract data with Claude
        plan.steps.append(ExecutionStep(
            id="step_5_extract",
            type=StepType.CLAUDE_REASON,
            name="Extract structured data",
            description="Use Claude to intelligently extract data from scraped content",
            depends_on=["step_1_firecrawl", "step_2_playwright", "step_3_http", "step_4_alternative"],
            params={"task": "extract", "intent": intent},
            timeout_seconds=30,
            output_key="extracted_data",
        ))
        plan.agents_used.append("claude")

    def _add_search_steps(self, plan: ExecutionPlan, intent: str, context: Dict):
        """Add steps for a search task."""

        # Step 1: Web search
        plan.steps.append(ExecutionStep(
            id="step_1_search",
            type=StepType.MCP_CALL,
            name="Web search",
            description="Search the web using Brave Search",
            mcp="brave-search",
            tool="brave_web_search",
            params={"query": intent},
            fallback_step="step_2_duckduckgo",
            timeout_seconds=30,
            output_key="search_results",
        ))
        plan.mcps_used.append("brave-search")

        # Step 2: Fallback search
        plan.steps.append(ExecutionStep(
            id="step_2_duckduckgo",
            type=StepType.HTTP_REQUEST,
            name="DuckDuckGo search",
            description="Fallback to DuckDuckGo if Brave unavailable",
            params={"provider": "duckduckgo", "query": intent},
            timeout_seconds=30,
            output_key="search_results",
        ))

        # Step 3: Summarize results
        plan.steps.append(ExecutionStep(
            id="step_3_summarize",
            type=StepType.CLAUDE_REASON,
            name="Summarize results",
            description="Use Claude to summarize and rank search results",
            depends_on=["step_1_search", "step_2_duckduckgo"],
            params={"task": "summarize"},
            timeout_seconds=30,
            output_key="summary",
        ))
        plan.agents_used.append("claude")

    def _add_automation_steps(self, plan: ExecutionPlan, intent: str, context: Dict):
        """Add steps for an automation task."""

        # Step 1: Search n8n templates
        plan.steps.append(ExecutionStep(
            id="step_1_templates",
            type=StepType.MCP_CALL,
            name="Search workflow templates",
            description="Find relevant n8n workflow templates",
            mcp="n8n",
            tool="search_templates",
            params={"query": intent},
            timeout_seconds=30,
            output_key="templates",
        ))
        plan.mcps_used.append("n8n")

        # Step 2: Create workflow
        plan.steps.append(ExecutionStep(
            id="step_2_create",
            type=StepType.MCP_CALL,
            name="Create workflow",
            description="Create the automation workflow",
            mcp="n8n",
            tool="create_workflow",
            depends_on=["step_1_templates"],
            params={"intent": intent},
            timeout_seconds=60,
            output_key="workflow",
        ))

        plan.agents_used.append("automation-agent")

    def _add_database_steps(self, plan: ExecutionPlan, intent: str, context: Dict):
        """Add steps for a database task."""

        # Step 1: Analyze query
        plan.steps.append(ExecutionStep(
            id="step_1_analyze",
            type=StepType.CLAUDE_REASON,
            name="Analyze database request",
            description="Understand what database operation is needed",
            params={"task": "analyze_db", "intent": intent},
            timeout_seconds=15,
            output_key="db_analysis",
        ))
        plan.agents_used.append("claude")

        # Step 2: Execute query
        plan.steps.append(ExecutionStep(
            id="step_2_query",
            type=StepType.MCP_CALL,
            name="Execute database query",
            description="Run the SQL query",
            mcp="postgresql",
            tool="query",
            depends_on=["step_1_analyze"],
            params={},
            timeout_seconds=30,
            output_key="query_results",
        ))
        plan.mcps_used.append("postgresql")

    def _add_general_steps(self, plan: ExecutionPlan, intent: str, context: Dict):
        """Add steps for a general task."""

        # Use Claude to figure it out
        plan.steps.append(ExecutionStep(
            id="step_1_reason",
            type=StepType.CLAUDE_REASON,
            name="Analyze and execute",
            description="Use Claude to understand and execute the task",
            params={"intent": intent, "context": context},
            timeout_seconds=120,
            output_key="result",
        ))
        plan.agents_used.append("claude")

    def _calculate_complexity(self, plan: ExecutionPlan) -> str:
        """Calculate plan complexity."""
        num_steps = len(plan.steps)
        num_mcps = len(plan.mcps_used)

        if num_steps <= 2 and num_mcps <= 1:
            return "simple"
        elif num_steps <= 4 and num_mcps <= 2:
            return "moderate"
        else:
            return "complex"

    def _save_plan(self, plan: ExecutionPlan):
        """Save plan to disk for debugging and reuse."""
        plan_file = self.plans_dir / f"{plan.id}.json"
        with open(plan_file, 'w', encoding='utf-8') as f:
            json.dump(plan.to_dict(), f, indent=2, ensure_ascii=False)

    def load_plan(self, plan_id: str) -> Optional[ExecutionPlan]:
        """Load a plan from disk."""
        plan_file = self.plans_dir / f"{plan_id}.json"
        if not plan_file.exists():
            return None

        with open(plan_file, encoding='utf-8') as f:
            data = json.load(f)

        # Reconstruct the plan
        steps = [
            ExecutionStep(
                id=s['id'],
                type=StepType(s['type']),
                name=s['name'],
                description=s['description'],
                mcp=s.get('mcp'),
                skill=s.get('skill'),
                agent=s.get('agent'),
                tool=s.get('tool'),
                params=s.get('params', {}),
                depends_on=s.get('depends_on', []),
                fallback_step=s.get('fallback_step'),
                timeout_seconds=s.get('timeout_seconds', 60),
                output_key=s.get('output_key'),
            )
            for s in data.get('steps', [])
        ]

        return ExecutionPlan(
            id=data['id'],
            intent=data['intent'],
            created_at=data['created_at'],
            complexity=data.get('complexity', 'simple'),
            estimated_duration_seconds=data.get('estimated_duration_seconds', 30),
            steps=steps,
            mcps_used=data.get('mcps_used', []),
            skills_used=data.get('skills_used', []),
            agents_used=data.get('agents_used', []),
            initial_context=data.get('initial_context', {}),
        )

    def find_similar_plan(self, intent: str) -> Optional[ExecutionPlan]:
        """Find a similar plan that could be reused."""
        # Simple keyword matching for now
        intent_words = set(intent.lower().split())

        best_match = None
        best_score = 0

        for plan_file in self.plans_dir.glob("plan_*.json"):
            try:
                plan = self.load_plan(plan_file.stem)
                if plan:
                    plan_words = set(plan.intent.lower().split())
                    overlap = len(intent_words & plan_words)
                    if overlap > best_score:
                        best_score = overlap
                        best_match = plan
            except:
                pass

        # Only return if significant overlap
        if best_score >= 3:
            return best_match
        return None


# Singleton
_planner: Optional[ExecutionPlanner] = None


def get_execution_planner() -> ExecutionPlanner:
    """Get the singleton execution planner."""
    global _planner
    if _planner is None:
        _planner = ExecutionPlanner()
    return _planner
