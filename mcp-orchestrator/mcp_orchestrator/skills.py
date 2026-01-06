"""
SDK Skill Definitions
"""

from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path


@dataclass
class Skill:
    """
    Skill configuration for custom skills.

    Example:
        my_skill = Skill(
            name="custom-extraction",
            description="Extract structured data from documents",
            tools=["Read", "Bash"],
            instructions="You are an expert at..."
        )
    """
    name: str
    description: str
    tools: List[str] = field(default_factory=list)
    instructions: str = ""
    examples: str = ""

    def to_markdown(self) -> str:
        """Convert skill to SKILL.md format."""
        tools_str = ", ".join(self.tools) if self.tools else ""

        content = f"""---
name: {self.name}
description: "{self.description}"
allowed-tools: {tools_str}
---

# {self.name.replace('-', ' ').title()}

## Instructions

{self.instructions}
"""
        if self.examples:
            content += f"""
## Examples

{self.examples}
"""
        return content

    def save(self, skills_dir: str = ".claude/skills"):
        """Save skill to file."""
        path = Path(skills_dir) / self.name
        path.mkdir(parents=True, exist_ok=True)
        (path / "SKILL.md").write_text(self.to_markdown())


# Pre-defined skills

WEB_SCRAPE_SKILL = Skill(
    name="web-scrape",
    description="Extract content from websites intelligently",
    tools=["Read", "Bash"],
    instructions="""
Extract content from websites using intelligent patterns.

1. Identify the page structure
2. Find relevant content sections
3. Extract headlines, articles, or data
4. Return structured results
""",
    examples="""
- Scrape headlines from bbc.com
- Extract product prices from amazon.com
- Get article content from medium.com
""",
)

WEB_SEARCH_SKILL = Skill(
    name="web-search",
    description="Search the web for information",
    tools=["Bash"],
    instructions="""
Search the web using available providers.

Priority:
1. Brave Search (if API key configured)
2. DuckDuckGo (may be blocked)
3. Specific site scraping as fallback
""",
)

API_DESIGN_SKILL = Skill(
    name="api-design",
    description="Design RESTful and GraphQL APIs",
    tools=["Read", "Write", "Edit"],
    instructions="""
Design APIs following REST best practices:
- Use nouns for resources
- Proper HTTP methods
- Correct status codes
- Request/response schemas
""",
)
