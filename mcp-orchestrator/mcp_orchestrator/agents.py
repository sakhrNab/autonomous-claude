"""
SDK Agent Definitions
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


class AgentType(Enum):
    """Available agent types."""
    PLANNING = "planning-agent"
    CODE = "code-agent"
    API = "api-agent"
    DB = "db-agent"
    TEST = "test-agent"
    CACHE = "cache-agent"
    AI = "ai-agent"
    SEARCH = "search-agent"
    SCRAPE = "scrape-agent"
    UI = "ui-agent"


@dataclass
class Agent:
    """
    Agent configuration for custom agents.

    Example:
        custom_agent = Agent(
            name="my-agent",
            description="Does something special",
            tools=["Read", "Write", "Bash"],
            prompt="You are a specialized agent..."
        )
    """
    name: str
    description: str
    tools: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    mcp: Optional[str] = None
    priority: int = 50
    prompt: str = ""
    can_delegate_to: List[str] = field(default_factory=list)
    hooks_after: List[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Convert agent to markdown format for .claude/agents/"""
        tools_str = ", ".join(self.tools) if self.tools else ""
        skills_str = ", ".join(self.skills) if self.skills else ""

        frontmatter = f"""---
name: {self.name}
description: "{self.description}"
tools: {tools_str}
model: sonnet
priority: {self.priority}
"""
        if skills_str:
            frontmatter += f"skills: {skills_str}\n"
        if self.mcp:
            frontmatter += f"mcp: {self.mcp}\n"
        frontmatter += "---\n\n"

        return frontmatter + self.prompt

    def save(self, agents_dir: str = ".claude/agents"):
        """Save agent to file."""
        from pathlib import Path
        path = Path(agents_dir)
        path.mkdir(parents=True, exist_ok=True)
        (path / f"{self.name}.md").write_text(self.to_markdown())


# Pre-defined agents
PLANNING_AGENT = Agent(
    name="planning-agent",
    description="Analyzes requests and creates execution plans",
    tools=["Read", "Grep", "Glob", "Bash"],
    priority=100,
)

CODE_AGENT = Agent(
    name="code-agent",
    description="Writes and modifies code",
    tools=["Read", "Write", "Edit", "Grep", "Glob", "Bash"],
    skills=["code-review", "security-check"],
    priority=90,
)

API_AGENT = Agent(
    name="api-agent",
    description="Creates REST/GraphQL APIs",
    tools=["Read", "Write", "Edit", "Bash"],
    skills=["api-design", "openapi-spec"],
    priority=85,
)

DB_AGENT = Agent(
    name="db-agent",
    description="Database operations and migrations",
    tools=["Read", "Write", "Edit", "Bash"],
    mcp="postgresql",
    skills=["sql-optimization", "schema-design"],
    priority=85,
)

TEST_AGENT = Agent(
    name="test-agent",
    description="Writes and runs tests",
    tools=["Read", "Write", "Edit", "Bash", "Grep"],
    skills=["test-patterns", "coverage-analysis"],
    priority=95,
)
