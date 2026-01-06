"""
Source of Truth - The Central Brain of the Autonomous System

This is the CONTENT TABLE that tells the entire system:
1. Which agent/skill/hook/MCP to use for each task type
2. When to search the web for latest info
3. When to check the database
4. How to route requests
5. When to create new capabilities

The Source of Truth is consulted BEFORE any task execution to determine:
- What capabilities are needed
- What order to execute them
- What hooks to trigger
- What to cache
- What to test

This follows the principle: "The system should always know what to do next"
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum


class CapabilityType(Enum):
    """Types of capabilities in the system."""
    AGENT = "agent"
    SKILL = "skill"
    HOOK = "hook"
    MCP = "mcp"
    COMMAND = "command"
    API = "api"


class TaskCategory(Enum):
    """Categories of tasks the system can handle."""
    WEB_SCRAPING = "web_scraping"
    WEB_SEARCH = "web_search"
    DATABASE = "database"
    FILE_OPERATION = "file_operation"
    API_CALL = "api_call"
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    TESTING = "testing"
    DEPLOYMENT = "deployment"
    UI_DESIGN = "ui_design"
    DOCUMENTATION = "documentation"
    PLANNING = "planning"
    CACHING = "caching"
    AUTHENTICATION = "authentication"
    PAYMENT = "payment"
    NOTIFICATION = "notification"
    MONITORING = "monitoring"
    UNKNOWN = "unknown"


@dataclass
class CapabilityEntry:
    """A single capability in the system."""
    name: str
    type: CapabilityType
    description: str
    triggers: List[str]  # Keywords/patterns that trigger this capability
    dependencies: List[str] = field(default_factory=list)
    hooks_before: List[str] = field(default_factory=list)
    hooks_after: List[str] = field(default_factory=list)
    requires_web_search: bool = False
    requires_db_check: bool = False
    requires_cache_check: bool = False
    auto_test: bool = True
    priority: int = 5  # 1-10, higher = more priority


@dataclass
class TaskRoutingRule:
    """A rule for routing tasks to capabilities."""
    pattern: str  # Regex or keyword pattern
    category: TaskCategory
    primary_capability: str
    fallback_capabilities: List[str] = field(default_factory=list)
    always_search_web: bool = False
    always_check_db: bool = False
    hooks_to_trigger: List[str] = field(default_factory=list)
    requires_planning: bool = True
    requires_testing: bool = True
    max_iterations: int = 10


@dataclass
class GuidanceDocument:
    """A guidance document for specific task types."""
    name: str
    category: TaskCategory
    content: str
    last_updated: str
    version: str = "1.0"


class SourceOfTruth:
    """
    The Central Brain - Source of Truth for the entire system.

    This class:
    1. Maintains the content table of all capabilities
    2. Routes tasks to appropriate agents/skills/hooks
    3. Decides when to search web, check DB, use cache
    4. Creates new capabilities when needed
    5. Updates itself based on learnings
    """

    def __init__(self):
        self.base_path = Path(__file__).parent.parent
        self.sot_path = self.base_path / "source_of_truth"
        self.sot_path.mkdir(parents=True, exist_ok=True)

        # Core registries
        self.capabilities: Dict[str, CapabilityEntry] = {}
        self.routing_rules: List[TaskRoutingRule] = []
        self.guidance_docs: Dict[str, GuidanceDocument] = {}

        # Load or initialize
        self._load_or_initialize()

    def _load_or_initialize(self):
        """Load existing SOT or initialize with defaults."""
        capabilities_file = self.sot_path / "capabilities.json"
        routing_file = self.sot_path / "routing_rules.json"

        if capabilities_file.exists():
            self._load_capabilities()
            self._load_routing_rules()
        else:
            self._initialize_defaults()
            self._save_all()

    def _initialize_defaults(self):
        """Initialize with default capabilities and routing rules."""

        # === AGENTS ===
        self.register_capability(CapabilityEntry(
            name="planning-agent",
            type=CapabilityType.AGENT,
            description="Analyzes tasks, creates plans, understands dependencies",
            triggers=["plan", "analyze", "understand", "design", "architect"],
            hooks_before=["load-context"],
            hooks_after=["save-plan", "update-todo"],
            requires_web_search=True,
            priority=10,
        ))

        self.register_capability(CapabilityEntry(
            name="code-agent",
            type=CapabilityType.AGENT,
            description="Writes, modifies, and reviews code",
            triggers=["code", "implement", "create", "build", "fix", "refactor"],
            hooks_before=["load-context", "check-design-patterns"],
            hooks_after=["run-tests", "update-todo"],
            requires_db_check=True,
            priority=8,
        ))

        self.register_capability(CapabilityEntry(
            name="testing-agent",
            type=CapabilityType.AGENT,
            description="Writes and runs tests, verifies functionality",
            triggers=["test", "verify", "check", "validate"],
            hooks_before=["load-test-config"],
            hooks_after=["report-results", "update-todo"],
            auto_test=False,  # It IS the test
            priority=9,
        ))

        self.register_capability(CapabilityEntry(
            name="ui-design-agent",
            type=CapabilityType.AGENT,
            description="Designs and implements UI following design system",
            triggers=["ui", "frontend", "design", "page", "component", "responsive"],
            hooks_before=["load-design-system", "check-ui-patterns"],
            hooks_after=["screenshot-test", "update-todo"],
            priority=7,
        ))

        self.register_capability(CapabilityEntry(
            name="database-agent",
            type=CapabilityType.AGENT,
            description="Handles database operations, schema, migrations",
            triggers=["database", "db", "sql", "schema", "migration", "query"],
            dependencies=["postgresql-mcp"],
            hooks_before=["backup-db"],
            hooks_after=["verify-migration", "update-todo"],
            requires_db_check=True,
            priority=8,
        ))

        # === SKILLS ===
        self.register_capability(CapabilityEntry(
            name="web-search",
            type=CapabilityType.SKILL,
            description="Searches the web for information",
            triggers=["search", "find", "lookup", "latest", "current"],
            requires_web_search=True,
            priority=7,
        ))

        self.register_capability(CapabilityEntry(
            name="web-scrape",
            type=CapabilityType.SKILL,
            description="Scrapes websites for data",
            triggers=["scrape", "extract", "crawl", "fetch from"],
            dependencies=["playwright-mcp"],
            priority=6,
        ))

        self.register_capability(CapabilityEntry(
            name="api-integration",
            type=CapabilityType.SKILL,
            description="Integrates with external APIs",
            triggers=["api", "endpoint", "rest", "graphql", "webhook"],
            hooks_after=["cache-response"],
            requires_cache_check=True,
            priority=7,
        ))

        self.register_capability(CapabilityEntry(
            name="file-operations",
            type=CapabilityType.SKILL,
            description="File system operations",
            triggers=["file", "read", "write", "create file", "delete file"],
            dependencies=["filesystem-mcp"],
            priority=5,
        ))

        # === HOOKS ===
        self.register_capability(CapabilityEntry(
            name="update-todo",
            type=CapabilityType.HOOK,
            description="Updates TODO.md after each task completion",
            triggers=["task-complete", "step-done"],
            priority=10,
        ))

        self.register_capability(CapabilityEntry(
            name="check-design-patterns",
            type=CapabilityType.HOOK,
            description="Verifies code follows design patterns",
            triggers=["before-code", "review"],
            priority=8,
        ))

        self.register_capability(CapabilityEntry(
            name="load-design-system",
            type=CapabilityType.HOOK,
            description="Loads UI design system before UI work",
            triggers=["before-ui", "ui-start"],
            priority=9,
        ))

        self.register_capability(CapabilityEntry(
            name="run-tests",
            type=CapabilityType.HOOK,
            description="Runs tests after code changes",
            triggers=["after-code", "verify"],
            priority=10,
        ))

        self.register_capability(CapabilityEntry(
            name="search-latest-version",
            type=CapabilityType.HOOK,
            description="Searches web for latest library/MCP versions",
            triggers=["new-library", "new-mcp", "install"],
            requires_web_search=True,
            priority=9,
        ))

        self.register_capability(CapabilityEntry(
            name="check-cache",
            type=CapabilityType.HOOK,
            description="Checks if data should be cached",
            triggers=["api-call", "db-query", "expensive-operation"],
            priority=7,
        ))

        self.register_capability(CapabilityEntry(
            name="backup-db",
            type=CapabilityType.HOOK,
            description="Creates DB backup before migrations",
            triggers=["before-migration", "schema-change"],
            priority=10,
        ))

        # === MCPs ===
        self.register_capability(CapabilityEntry(
            name="postgresql-mcp",
            type=CapabilityType.MCP,
            description="PostgreSQL database operations",
            triggers=["postgres", "postgresql", "sql database"],
            priority=8,
        ))

        self.register_capability(CapabilityEntry(
            name="playwright-mcp",
            type=CapabilityType.MCP,
            description="Browser automation for scraping",
            triggers=["browser", "playwright", "scrape javascript"],
            priority=7,
        ))

        self.register_capability(CapabilityEntry(
            name="brave-search-mcp",
            type=CapabilityType.MCP,
            description="Web search via Brave Search",
            triggers=["web search", "search online"],
            priority=7,
        ))

        self.register_capability(CapabilityEntry(
            name="filesystem-mcp",
            type=CapabilityType.MCP,
            description="File system operations",
            triggers=["file", "directory", "filesystem"],
            priority=6,
        ))

        # === ROUTING RULES ===
        self.add_routing_rule(TaskRoutingRule(
            pattern=r"(plan|design|architect|analyze)",
            category=TaskCategory.PLANNING,
            primary_capability="planning-agent",
            always_search_web=True,
            hooks_to_trigger=["load-context"],
            requires_planning=False,  # It IS the planning
        ))

        self.add_routing_rule(TaskRoutingRule(
            pattern=r"(scrape|crawl|extract from|get from website)",
            category=TaskCategory.WEB_SCRAPING,
            primary_capability="web-scrape",
            fallback_capabilities=["web-search"],
            hooks_to_trigger=["check-cache"],
        ))

        self.add_routing_rule(TaskRoutingRule(
            pattern=r"(search|find|lookup|what is|how to)",
            category=TaskCategory.WEB_SEARCH,
            primary_capability="web-search",
            always_search_web=True,
        ))

        self.add_routing_rule(TaskRoutingRule(
            pattern=r"(database|db|sql|query|migration|schema)",
            category=TaskCategory.DATABASE,
            primary_capability="database-agent",
            always_check_db=True,
            hooks_to_trigger=["backup-db", "check-cache"],
        ))

        self.add_routing_rule(TaskRoutingRule(
            pattern=r"(ui|frontend|page|component|design|responsive)",
            category=TaskCategory.UI_DESIGN,
            primary_capability="ui-design-agent",
            hooks_to_trigger=["load-design-system", "check-design-patterns"],
        ))

        self.add_routing_rule(TaskRoutingRule(
            pattern=r"(test|verify|check|validate|assert)",
            category=TaskCategory.TESTING,
            primary_capability="testing-agent",
            requires_testing=False,  # It IS the testing
        ))

        self.add_routing_rule(TaskRoutingRule(
            pattern=r"(api|endpoint|rest|graphql)",
            category=TaskCategory.API_CALL,
            primary_capability="api-integration",
            always_check_db=True,
            hooks_to_trigger=["check-cache"],
        ))

        self.add_routing_rule(TaskRoutingRule(
            pattern=r"(code|implement|create|build|fix|refactor)",
            category=TaskCategory.CODE_GENERATION,
            primary_capability="code-agent",
            hooks_to_trigger=["check-design-patterns", "run-tests"],
        ))

    def register_capability(self, capability: CapabilityEntry):
        """Register a new capability."""
        self.capabilities[capability.name] = capability

    def add_routing_rule(self, rule: TaskRoutingRule):
        """Add a new routing rule."""
        self.routing_rules.append(rule)

    def route_task(self, task_description: str) -> Dict[str, Any]:
        """
        Route a task to the appropriate capabilities.

        This is the MAIN ENTRY POINT for the system.
        Returns a complete execution plan.
        """
        import re

        task_lower = task_description.lower()

        # Find matching routing rule
        matched_rule = None
        for rule in self.routing_rules:
            if re.search(rule.pattern, task_lower, re.IGNORECASE):
                matched_rule = rule
                break

        if not matched_rule:
            # Default to planning agent for unknown tasks
            matched_rule = TaskRoutingRule(
                pattern=".*",
                category=TaskCategory.UNKNOWN,
                primary_capability="planning-agent",
                always_search_web=True,
                requires_planning=True,
            )

        # Get primary capability
        primary_cap = self.capabilities.get(matched_rule.primary_capability)

        # Build execution plan
        execution_plan = {
            "task": task_description,
            "category": matched_rule.category.value,
            "primary_capability": matched_rule.primary_capability,
            "fallback_capabilities": matched_rule.fallback_capabilities,

            # Pre-execution checks
            "search_web_first": matched_rule.always_search_web or (primary_cap and primary_cap.requires_web_search),
            "check_db_first": matched_rule.always_check_db or (primary_cap and primary_cap.requires_db_check),
            "check_cache_first": primary_cap.requires_cache_check if primary_cap else False,

            # Hooks
            "hooks_before": (primary_cap.hooks_before if primary_cap else []) + matched_rule.hooks_to_trigger,
            "hooks_after": primary_cap.hooks_after if primary_cap else ["update-todo"],

            # Execution settings
            "requires_planning": matched_rule.requires_planning,
            "requires_testing": matched_rule.requires_testing,
            "max_iterations": matched_rule.max_iterations,
            "auto_test": primary_cap.auto_test if primary_cap else True,

            # Dependencies
            "dependencies": primary_cap.dependencies if primary_cap else [],
        }

        return execution_plan

    def should_create_new_capability(self, task_description: str) -> Tuple[bool, str]:
        """
        Determine if we need to create a new capability for this task.

        Returns (should_create, reason)
        """
        plan = self.route_task(task_description)

        if plan["category"] == TaskCategory.UNKNOWN.value:
            return True, "Task doesn't match any existing capabilities"

        # Check if primary capability exists
        if plan["primary_capability"] not in self.capabilities:
            return True, f"Primary capability '{plan['primary_capability']}' doesn't exist"

        return False, "Existing capabilities can handle this task"

    def create_new_capability(self, name: str, type_: CapabilityType, description: str, triggers: List[str]) -> CapabilityEntry:
        """Dynamically create a new capability."""
        capability = CapabilityEntry(
            name=name,
            type=type_,
            description=description,
            triggers=triggers,
            hooks_after=["update-todo"],
            auto_test=True,
        )
        self.register_capability(capability)
        self._save_all()
        return capability

    def get_guidance(self, category: TaskCategory) -> Optional[str]:
        """Get guidance document for a task category."""
        doc = self.guidance_docs.get(category.value)
        return doc.content if doc else None

    def add_guidance(self, category: TaskCategory, content: str):
        """Add or update a guidance document."""
        self.guidance_docs[category.value] = GuidanceDocument(
            name=f"{category.value}_guidance",
            category=category,
            content=content,
            last_updated=datetime.now().isoformat(),
        )
        self._save_guidance()

    def _save_all(self):
        """Save all SOT data."""
        # Save capabilities
        caps_data = {name: asdict(cap) for name, cap in self.capabilities.items()}
        for cap in caps_data.values():
            cap["type"] = cap["type"].value

        with open(self.sot_path / "capabilities.json", "w") as f:
            json.dump(caps_data, f, indent=2)

        # Save routing rules
        rules_data = [asdict(rule) for rule in self.routing_rules]
        for rule in rules_data:
            rule["category"] = rule["category"].value

        with open(self.sot_path / "routing_rules.json", "w") as f:
            json.dump(rules_data, f, indent=2)

    def _load_capabilities(self):
        """Load capabilities from file."""
        with open(self.sot_path / "capabilities.json") as f:
            data = json.load(f)

        for name, cap_data in data.items():
            cap_data["type"] = CapabilityType(cap_data["type"])
            self.capabilities[name] = CapabilityEntry(**cap_data)

    def _load_routing_rules(self):
        """Load routing rules from file."""
        rules_file = self.sot_path / "routing_rules.json"
        if not rules_file.exists():
            return

        with open(rules_file) as f:
            data = json.load(f)

        for rule_data in data:
            rule_data["category"] = TaskCategory(rule_data["category"])
            self.routing_rules.append(TaskRoutingRule(**rule_data))

    def _save_guidance(self):
        """Save guidance documents."""
        docs_data = {name: asdict(doc) for name, doc in self.guidance_docs.items()}
        for doc in docs_data.values():
            doc["category"] = doc["category"].value

        with open(self.sot_path / "guidance.json", "w") as f:
            json.dump(docs_data, f, indent=2)


# Singleton instance
_sot: Optional[SourceOfTruth] = None


def get_source_of_truth() -> SourceOfTruth:
    """Get the singleton Source of Truth instance."""
    global _sot
    if _sot is None:
        _sot = SourceOfTruth()
    return _sot


def route_task(task_description: str) -> Dict[str, Any]:
    """Convenience function to route a task."""
    return get_source_of_truth().route_task(task_description)
