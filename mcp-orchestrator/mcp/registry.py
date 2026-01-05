"""
MCP Registry

Maintains a registry of all known MCP servers with their capabilities.
This enables the autonomous operator to:
1. Know what tools are available
2. Match user intent to required MCPs
3. Auto-install MCPs when needed
4. Stay aware of new MCPs

Sources:
- modelcontextprotocol/servers (official)
- wong2/awesome-mcp-servers
- appcypher/awesome-mcp-servers
- cnych/claude-mcp
- czlonkowski/n8n-mcp
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import json
import re


class MCPCategory(Enum):
    """Categories of MCP servers."""
    BROWSER = "browser"           # Playwright, Puppeteer, Browserbase
    DATABASE = "database"         # PostgreSQL, SQLite, MongoDB
    SEARCH = "search"             # Exa, Tavily, Brave Search
    FILESYSTEM = "filesystem"     # File operations, Git
    DEVOPS = "devops"             # GitHub, Docker, Kubernetes
    WORKFLOW = "workflow"         # n8n, Make, Zapier
    COMMUNICATION = "communication"  # Slack, Email, Telegram
    AI_TOOLS = "ai_tools"         # Langfuse, Chroma
    SCRAPING = "scraping"         # Firecrawl, Apify, Crawlbase
    DOCS = "docs"                 # Context7, documentation tools
    UTILITY = "utility"           # General utilities
    CLOUD = "cloud"               # AWS, GCP, Cloudflare


@dataclass
class MCPCapability:
    """A specific capability provided by an MCP."""
    name: str
    description: str
    keywords: List[str]  # Keywords that trigger this capability
    required_params: List[str] = field(default_factory=list)
    optional_params: List[str] = field(default_factory=list)


@dataclass
class MCPServer:
    """An MCP server definition."""
    name: str
    package: str  # npm package or GitHub repo
    description: str
    category: MCPCategory
    capabilities: List[MCPCapability]
    install_command: str
    config_template: Dict[str, Any]
    keywords: List[str]  # Keywords that suggest this MCP is needed
    dependencies: List[str] = field(default_factory=list)
    official: bool = False
    popularity: int = 0  # Stars or usage count
    last_updated: Optional[datetime] = None

    def matches_intent(self, intent: str) -> float:
        """Score how well this MCP matches a user intent."""
        intent_lower = intent.lower()
        score = 0.0

        # Check keywords
        for keyword in self.keywords:
            if keyword.lower() in intent_lower:
                score += 0.2

        # Check capability keywords
        for cap in self.capabilities:
            for kw in cap.keywords:
                if kw.lower() in intent_lower:
                    score += 0.15

        # Check name and description
        if self.name.lower() in intent_lower:
            score += 0.3
        for word in self.description.lower().split():
            if len(word) > 4 and word in intent_lower:
                score += 0.05

        return min(1.0, score)


class MCPRegistry:
    """
    Registry of all known MCP servers.

    This is the brain for capability awareness.
    """

    def __init__(self, storage_path: str = "state/mcp_registry.json"):
        self.storage_path = Path(storage_path)
        self.servers: Dict[str, MCPServer] = {}
        self.installed: Set[str] = set()
        self._initialize_builtin_servers()
        self._load()

    def _initialize_builtin_servers(self):
        """Initialize with known MCP servers."""

        # Playwright - Browser automation
        self.register(MCPServer(
            name="playwright",
            package="@anthropic/mcp-server-playwright",
            description="Browser automation for web scraping, testing, and interaction",
            category=MCPCategory.BROWSER,
            capabilities=[
                MCPCapability(
                    name="navigate",
                    description="Navigate to URLs",
                    keywords=["browse", "visit", "open", "go to", "navigate"],
                ),
                MCPCapability(
                    name="scrape",
                    description="Scrape web page content",
                    keywords=["scrape", "extract", "get content", "crawl", "parse"],
                ),
                MCPCapability(
                    name="screenshot",
                    description="Take screenshots of pages",
                    keywords=["screenshot", "capture", "image", "snapshot"],
                ),
                MCPCapability(
                    name="interact",
                    description="Click, type, and interact with elements",
                    keywords=["click", "type", "fill", "submit", "interact", "form"],
                ),
            ],
            install_command="npm install -g @anthropic/mcp-server-playwright",
            config_template={
                "command": "npx",
                "args": ["-y", "@anthropic/mcp-server-playwright"],
            },
            keywords=["browser", "web", "scrape", "automation", "playwright", "website", "page"],
            official=True,
        ))

        # PostgreSQL - Database
        self.register(MCPServer(
            name="postgresql",
            package="@anthropic/mcp-server-postgres",
            description="PostgreSQL database integration with schema inspection and queries",
            category=MCPCategory.DATABASE,
            capabilities=[
                MCPCapability(
                    name="query",
                    description="Execute SQL queries",
                    keywords=["query", "sql", "select", "database"],
                ),
                MCPCapability(
                    name="schema",
                    description="Inspect database schema",
                    keywords=["schema", "tables", "columns", "structure"],
                ),
            ],
            install_command="npm install -g @anthropic/mcp-server-postgres",
            config_template={
                "command": "npx",
                "args": ["-y", "@anthropic/mcp-server-postgres", "postgresql://user:pass@host:5432/db"],
            },
            keywords=["postgres", "postgresql", "database", "sql", "db"],
            official=True,
        ))

        # n8n - Workflow automation
        self.register(MCPServer(
            name="n8n",
            package="n8n-mcp",
            description="AI-powered workflow automation with 543 nodes and 2709 templates",
            category=MCPCategory.WORKFLOW,
            capabilities=[
                MCPCapability(
                    name="search_nodes",
                    description="Search n8n nodes",
                    keywords=["workflow", "automation", "node", "n8n"],
                ),
                MCPCapability(
                    name="create_workflow",
                    description="Create and manage workflows",
                    keywords=["workflow", "automate", "flow", "process"],
                ),
                MCPCapability(
                    name="templates",
                    description="Access workflow templates",
                    keywords=["template", "preset", "example"],
                ),
            ],
            install_command="npx n8n-mcp",
            config_template={
                "command": "npx",
                "args": ["n8n-mcp"],
                "env": {"MCP_MODE": "stdio"},
            },
            keywords=["n8n", "workflow", "automation", "integrate", "process", "flow"],
        ))

        # Context7 - Documentation
        self.register(MCPServer(
            name="context7",
            package="@upstash/context7-mcp",
            description="Up-to-date documentation for any prompt",
            category=MCPCategory.DOCS,
            capabilities=[
                MCPCapability(
                    name="get_docs",
                    description="Get latest documentation",
                    keywords=["docs", "documentation", "library", "api", "reference"],
                ),
            ],
            install_command="npm install -g @upstash/context7-mcp",
            config_template={
                "command": "npx",
                "args": ["-y", "@upstash/context7-mcp"],
            },
            keywords=["docs", "documentation", "latest", "library", "api", "reference", "context7"],
        ))

        # Filesystem
        self.register(MCPServer(
            name="filesystem",
            package="@modelcontextprotocol/server-filesystem",
            description="Secure file operations with configurable access controls",
            category=MCPCategory.FILESYSTEM,
            capabilities=[
                MCPCapability(
                    name="read_file",
                    description="Read file contents",
                    keywords=["read", "file", "content", "open"],
                ),
                MCPCapability(
                    name="write_file",
                    description="Write file contents",
                    keywords=["write", "save", "create", "file"],
                ),
                MCPCapability(
                    name="list_files",
                    description="List directory contents",
                    keywords=["list", "directory", "folder", "files"],
                ),
            ],
            install_command="npm install -g @modelcontextprotocol/server-filesystem",
            config_template={
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed"],
            },
            keywords=["file", "filesystem", "read", "write", "directory"],
            official=True,
        ))

        # GitHub
        self.register(MCPServer(
            name="github",
            package="@modelcontextprotocol/server-github",
            description="GitHub API integration for repository management",
            category=MCPCategory.DEVOPS,
            capabilities=[
                MCPCapability(
                    name="repos",
                    description="Manage repositories",
                    keywords=["repo", "repository", "github", "git"],
                ),
                MCPCapability(
                    name="issues",
                    description="Manage issues",
                    keywords=["issue", "bug", "ticket", "task"],
                ),
                MCPCapability(
                    name="prs",
                    description="Manage pull requests",
                    keywords=["pr", "pull request", "merge", "review"],
                ),
            ],
            install_command="npm install -g @modelcontextprotocol/server-github",
            config_template={
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-github"],
                "env": {"GITHUB_TOKEN": "your-token"},
            },
            keywords=["github", "git", "repo", "repository", "pr", "issue"],
            official=True,
        ))

        # Brave Search
        self.register(MCPServer(
            name="brave-search",
            package="@modelcontextprotocol/server-brave-search",
            description="Web search using Brave Search API",
            category=MCPCategory.SEARCH,
            capabilities=[
                MCPCapability(
                    name="search",
                    description="Search the web",
                    keywords=["search", "find", "lookup", "google", "web"],
                ),
            ],
            install_command="npm install -g @modelcontextprotocol/server-brave-search",
            config_template={
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-brave-search"],
                "env": {"BRAVE_API_KEY": "your-key"},
            },
            keywords=["search", "web", "find", "lookup", "browse", "google"],
            official=True,
        ))

        # Firecrawl - Advanced scraping
        self.register(MCPServer(
            name="firecrawl",
            package="firecrawl-mcp",
            description="Advanced web scraping and crawling with JS rendering",
            category=MCPCategory.SCRAPING,
            capabilities=[
                MCPCapability(
                    name="crawl",
                    description="Crawl websites",
                    keywords=["crawl", "scrape", "spider", "extract"],
                ),
                MCPCapability(
                    name="extract",
                    description="Extract structured data",
                    keywords=["extract", "parse", "data", "content"],
                ),
            ],
            install_command="npm install -g firecrawl-mcp",
            config_template={
                "command": "npx",
                "args": ["firecrawl-mcp"],
                "env": {"FIRECRAWL_API_KEY": "your-key"},
            },
            keywords=["crawl", "scrape", "spider", "firecrawl", "extract", "website"],
        ))

        # Slack
        self.register(MCPServer(
            name="slack",
            package="@modelcontextprotocol/server-slack",
            description="Slack workspace integration",
            category=MCPCategory.COMMUNICATION,
            capabilities=[
                MCPCapability(
                    name="send_message",
                    description="Send messages to channels",
                    keywords=["message", "send", "post", "notify"],
                ),
                MCPCapability(
                    name="read_messages",
                    description="Read channel messages",
                    keywords=["read", "messages", "history", "channel"],
                ),
            ],
            install_command="npm install -g @modelcontextprotocol/server-slack",
            config_template={
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-slack"],
                "env": {"SLACK_BOT_TOKEN": "xoxb-your-token"},
            },
            keywords=["slack", "message", "channel", "notify", "team"],
            official=True,
        ))

        # Docker
        self.register(MCPServer(
            name="docker",
            package="docker-mcp",
            description="Run and manage Docker containers",
            category=MCPCategory.DEVOPS,
            capabilities=[
                MCPCapability(
                    name="containers",
                    description="Manage containers",
                    keywords=["container", "docker", "run", "start", "stop"],
                ),
                MCPCapability(
                    name="images",
                    description="Manage images",
                    keywords=["image", "build", "pull", "push"],
                ),
            ],
            install_command="npm install -g docker-mcp",
            config_template={
                "command": "npx",
                "args": ["docker-mcp"],
            },
            keywords=["docker", "container", "image", "run", "deploy"],
        ))

        # Apify - Web scraping platform
        self.register(MCPServer(
            name="apify",
            package="@apify/mcp-server",
            description="4000+ pre-built tools for web data extraction",
            category=MCPCategory.SCRAPING,
            capabilities=[
                MCPCapability(
                    name="actors",
                    description="Run Apify actors",
                    keywords=["actor", "scraper", "crawler", "extractor"],
                ),
            ],
            install_command="npm install -g @apify/mcp-server",
            config_template={
                "command": "npx",
                "args": ["-y", "@apify/mcp-server"],
                "env": {"APIFY_TOKEN": "your-token"},
            },
            keywords=["apify", "actor", "scrape", "extract", "crawl"],
        ))

        # Make (Integromat)
        self.register(MCPServer(
            name="make",
            package="make-mcp-server",
            description="Turn Make scenarios into callable tools",
            category=MCPCategory.WORKFLOW,
            capabilities=[
                MCPCapability(
                    name="scenarios",
                    description="Run Make scenarios",
                    keywords=["scenario", "automation", "integrate"],
                ),
            ],
            install_command="npm install -g make-mcp-server",
            config_template={
                "command": "npx",
                "args": ["make-mcp-server"],
                "env": {"MAKE_API_KEY": "your-key"},
            },
            keywords=["make", "integromat", "scenario", "automation", "integrate"],
        ))

        # Exa - AI search
        self.register(MCPServer(
            name="exa",
            package="@exa/mcp-server",
            description="Search engine made for AIs",
            category=MCPCategory.SEARCH,
            capabilities=[
                MCPCapability(
                    name="search",
                    description="AI-powered search",
                    keywords=["search", "find", "lookup", "query"],
                ),
            ],
            install_command="npm install -g @exa/mcp-server",
            config_template={
                "command": "npx",
                "args": ["-y", "@exa/mcp-server"],
                "env": {"EXA_API_KEY": "your-key"},
            },
            keywords=["exa", "search", "ai", "find", "semantic"],
        ))

    def register(self, server: MCPServer):
        """Register an MCP server."""
        self.servers[server.name] = server
        self._save()

    def get(self, name: str) -> Optional[MCPServer]:
        """Get an MCP server by name."""
        return self.servers.get(name)

    def find_for_intent(self, intent: str, top_k: int = 3) -> List[tuple]:
        """Find MCPs that match a user intent."""
        scores = []
        for name, server in self.servers.items():
            score = server.matches_intent(intent)
            if score > 0.1:
                scores.append((server, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def get_by_category(self, category: MCPCategory) -> List[MCPServer]:
        """Get all MCPs in a category."""
        return [s for s in self.servers.values() if s.category == category]

    def is_installed(self, name: str) -> bool:
        """Check if an MCP is installed."""
        return name in self.installed

    def mark_installed(self, name: str):
        """Mark an MCP as installed."""
        self.installed.add(name)
        self._save()

    def get_install_command(self, name: str) -> Optional[str]:
        """Get install command for an MCP."""
        server = self.get(name)
        return server.install_command if server else None

    def get_config(self, name: str) -> Optional[Dict[str, Any]]:
        """Get configuration template for an MCP."""
        server = self.get(name)
        return server.config_template if server else None

    def list_all(self) -> List[str]:
        """List all registered MCP names."""
        return list(self.servers.keys())

    def get_capabilities_summary(self) -> Dict[str, List[str]]:
        """Get a summary of all capabilities by category."""
        summary = {}
        for category in MCPCategory:
            servers = self.get_by_category(category)
            capabilities = []
            for server in servers:
                for cap in server.capabilities:
                    capabilities.extend(cap.keywords)
            summary[category.value] = list(set(capabilities))
        return summary

    def _load(self):
        """Load registry from storage."""
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                self.installed = set(data.get("installed", []))
                # Custom servers would be loaded here
            except Exception:
                pass

    def _save(self):
        """Save registry to storage."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "installed": list(self.installed),
            "server_count": len(self.servers),
            "last_updated": datetime.now().isoformat(),
        }
        self.storage_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def export_for_context(self) -> str:
        """Export registry summary for Claude's context."""
        lines = ["# Available MCP Servers\n"]

        for category in MCPCategory:
            servers = self.get_by_category(category)
            if servers:
                lines.append(f"\n## {category.value.title()}")
                for server in servers:
                    status = "[installed]" if self.is_installed(server.name) else ""
                    lines.append(f"- **{server.name}** {status}: {server.description}")

        return "\n".join(lines)
