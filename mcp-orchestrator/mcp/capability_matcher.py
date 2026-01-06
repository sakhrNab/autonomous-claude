"""
Capability Matcher

Matches user intent to required MCPs, skills, and hooks.
This enables the autonomous operator to understand:
"scrape this site" → needs Playwright MCP

Also handles:
- Auto-detection of missing capabilities
- Suggestion of MCPs to install
- Dynamic capability routing
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import re

from .registry import MCPRegistry, MCPServer, MCPCategory


@dataclass
class CapabilityMatch:
    """A matched capability."""
    mcp_name: str
    capability: str
    confidence: float
    is_installed: bool
    install_command: Optional[str]
    config: Optional[Dict[str, Any]]


@dataclass
class IntentAnalysis:
    """Analysis of user intent."""
    original_intent: str
    task_type: str  # scrape, query, automate, search, etc.
    required_mcps: List[CapabilityMatch]
    optional_mcps: List[CapabilityMatch]
    missing_mcps: List[CapabilityMatch]
    suggested_skills: List[str]
    suggested_hooks: List[str]
    confidence: float


class CapabilityMatcher:
    """
    Matches user intent to system capabilities.

    This is the "brain" that understands what the user wants
    and figures out what tools are needed.
    """

    def __init__(self, registry: Optional[MCPRegistry] = None):
        self.registry = registry or MCPRegistry()

        # Intent patterns -> task types
        self.intent_patterns = {
            "scrape": [
                r"scrape\s+",  # Any scrape intent
                r"scrape\s+(?:this\s+)?(?:the\s+)?(?:website|site|page|url)",
                r"scrape\s+.+\s+from",  # scrape X from Y
                r"extract\s+(?:data\s+)?from",
                r"crawl\s+(?:this\s+)?(?:the\s+)?",
                r"get\s+(?:the\s+)?content\s+from",
                r"parse\s+(?:this\s+)?(?:the\s+)?",
                r"fetch\s+(?:data\s+)?from",
            ],
            "database": [
                r"query\s+(?:the\s+)?database",
                r"select\s+(?:from|all|\*)",
                r"(?:insert|update|delete)\s+(?:into|from)?",
                r"(?:postgres|mysql|sqlite|mongodb)",
                r"run\s+(?:this\s+)?sql",
            ],
            "search": [
                # Direct search commands
                r"^search\b",
                r"search\s+",
                r"^find\b",
                r"find\s+",
                r"^look\s*(?:up|for|ing)",
                r"^google\b",

                # Questions - these are almost always searches
                r"^what\s+",
                r"^where\s+",
                r"^how\s+",
                r"^who\s+",
                r"^when\s+",
                r"^why\s+",
                r"^which\s+",
                r"^can\s+(?:i|you)",
                r"^is\s+there",
                r"^are\s+there",

                # Requests for information
                r"^(?:give|show|get|tell)\s+me",
                r"^i\s+(?:want|need|looking\s+for)",
                r"^(?:i'm|im)\s+looking\s+for",

                # Shopping/price queries
                r"cheap(?:est)?\s+",
                r"best\s+",
                r"top\s+\d*",
                r"price[s]?\s+",
                r"cost\s+(?:of|for)",
                r"buy\s+",
                r"shop\s+(?:for)?",
                r"purchase\s+",
                r"order\s+",
                r"compare\s+",
                r"review[s]?\s+",
                r"rating[s]?\s+",
                r"recommend",

                # Location-based queries
                r"(?:in|near|around)\s+\w+$",  # ends with "in berlin", "near tokyo"
                r"(?:restaurants?|hotels?|shops?|stores?|places?)\s+(?:in|near)",
            ],
            "automate": [
                r"automate\s+(?:this|the)",
                r"create\s+(?:a\s+)?workflow",
                r"schedule\s+(?:this|a)",
                r"run\s+(?:this\s+)?(?:every|daily|weekly)",
                r"set\s+up\s+(?:a\s+)?(?:pipeline|flow)",
            ],
            "deploy": [
                r"deploy\s+",  # Any deploy intent
                r"deploy\s+(?:this|to|the)",
                r"deploy\s+.+\s+to\s+(?:production|staging)",
                r"push\s+to\s+(?:production|staging)",
                r"release\s+(?:this|version)",
                r"ship\s+(?:this|it)",
            ],
            "notify": [
                r"send\s+(?:a\s+)?(?:message|notification|alert)",
                r"notify\s+(?:me|team|channel)",
                r"post\s+(?:to|in)\s+(?:slack|channel)",
                r"alert\s+(?:when|if)",
            ],
            "monitor": [
                r"monitor\s+(?:this|the)",
                r"watch\s+(?:for|this)",
                r"keep\s+(?:an\s+)?eye\s+on",
                r"track\s+(?:this|the)",
                r"alert\s+(?:me\s+)?(?:if|when)",
            ],
            "file": [
                r"read\s+(?:this\s+)?file",
                r"write\s+(?:to\s+)?file",
                r"create\s+(?:a\s+)?file",
                r"list\s+(?:the\s+)?(?:files|directory)",
                r"move\s+(?:this\s+)?file",
            ],
            "git": [
                r"(?:git\s+)?(?:commit|push|pull|merge)",
                r"create\s+(?:a\s+)?(?:pr|pull\s+request|branch)",
                r"(?:open|close)\s+(?:an?\s+)?issue",
                r"review\s+(?:the\s+)?(?:pr|code)",
            ],
            "docs": [
                r"(?:get|find|check|read)\s+(?:the\s+)?(?:docs|documentation)",
                r"read\s+(?:the\s+)?documentation",
                r"how\s+(?:do\s+I|to)\s+use",
                r"what\s+(?:is|are)\s+the\s+(?:api|methods)",
                r"latest\s+(?:version|docs)",
            ],
        }

        # Task type → required MCPs
        self.task_mcp_map = {
            "scrape": ["playwright", "firecrawl", "apify"],
            "database": ["postgresql", "sqlite", "mongodb"],
            "search": ["brave-search", "exa", "tavily"],
            "automate": ["n8n", "make", "zapier"],
            "deploy": ["docker", "kubernetes", "github"],
            "notify": ["slack", "telegram", "email"],
            "monitor": ["prometheus", "datadog", "cloudwatch"],
            "file": ["filesystem"],
            "git": ["github", "git"],
            "docs": ["context7"],
        }

        # Skills that can help with tasks
        self.task_skill_map = {
            "scrape": ["run-workflow", "fetch-logs"],
            "database": ["query-status", "run-pipeline"],
            "automate": ["run-workflow", "create-task-ledger"],
            "deploy": ["run-pipeline", "apply-fix"],
            "notify": ["send-notification"],
            "monitor": ["query-status", "fetch-logs"],
        }

    def analyze_intent(self, intent: str) -> IntentAnalysis:
        """
        Analyze user intent and determine required capabilities.

        Example:
        "scrape this website for product prices"
        →
        IntentAnalysis(
            task_type="scrape",
            required_mcps=[playwright],
            ...
        )
        """
        intent_lower = intent.lower()

        # Detect task type
        task_type = self._detect_task_type(intent_lower)

        # Get required MCPs for this task
        required_mcp_names = self.task_mcp_map.get(task_type, [])

        # Also check registry for additional matches
        registry_matches = self.registry.find_for_intent(intent)

        # Build capability matches
        required_mcps = []
        optional_mcps = []
        missing_mcps = []

        # Add primary MCPs - task can proceed if ANY ONE is installed
        seen_mcps = set()
        has_any_installed = False

        for mcp_name in required_mcp_names[:3]:  # Check top 3
            match = self._create_match(mcp_name)
            if match:
                seen_mcps.add(mcp_name)
                if match.is_installed:
                    required_mcps.append(match)
                    has_any_installed = True
                else:
                    # Only add to missing if we don't have ANY installed
                    optional_mcps.append(match)  # Treat as optional suggestion

        # If no primary MCPs are installed, mark first one as missing (required)
        if not has_any_installed and optional_mcps:
            missing_mcps.append(optional_mcps.pop(0))

        # Add registry matches as optional
        for server, score in registry_matches:
            if server.name not in seen_mcps and score > 0.2:
                match = self._create_match(server.name)
                if match:
                    if match.is_installed:
                        optional_mcps.append(match)
                    elif score > 0.4 and not has_any_installed:
                        missing_mcps.append(match)

        # Get suggested skills
        suggested_skills = self.task_skill_map.get(task_type, [])

        # Determine hooks needed
        suggested_hooks = self._get_suggested_hooks(task_type)

        # Calculate confidence
        confidence = self._calculate_confidence(
            task_type, required_mcps, missing_mcps, intent
        )

        return IntentAnalysis(
            original_intent=intent,
            task_type=task_type,
            required_mcps=required_mcps,
            optional_mcps=optional_mcps,
            missing_mcps=missing_mcps,
            suggested_skills=suggested_skills,
            suggested_hooks=suggested_hooks,
            confidence=confidence,
        )

    def _detect_task_type(self, intent: str) -> str:
        """Detect the primary task type from intent."""
        best_match = "general"
        best_score = 0

        for task_type, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, intent, re.IGNORECASE):
                    score = len(pattern)  # Longer patterns = more specific
                    if score > best_score:
                        best_score = score
                        best_match = task_type

        return best_match

    def _create_match(self, mcp_name: str) -> Optional[CapabilityMatch]:
        """Create a capability match for an MCP."""
        server = self.registry.get(mcp_name)
        if not server:
            return None

        return CapabilityMatch(
            mcp_name=mcp_name,
            capability=server.capabilities[0].name if server.capabilities else "general",
            confidence=0.8,
            is_installed=self.registry.is_installed(mcp_name),
            install_command=server.install_command,
            config=server.config_template,
        )

    def _get_suggested_hooks(self, task_type: str) -> List[str]:
        """Get suggested hooks for a task type."""
        hooks = ["task-ledger-update"]  # Always update task ledger

        if task_type in ["scrape", "automate", "deploy"]:
            hooks.append("completion-checker")

        if task_type in ["deploy", "database"]:
            hooks.append("intelligent-router")  # Risk assessment

        return hooks

    def _calculate_confidence(
        self,
        task_type: str,
        required_mcps: List[CapabilityMatch],
        missing_mcps: List[CapabilityMatch],
        intent: str
    ) -> float:
        """Calculate confidence in the analysis."""
        confidence = 0.5

        # Higher confidence if we detected a specific task type
        if task_type != "general":
            confidence += 0.2

        # Higher confidence if required MCPs are installed
        if required_mcps and not missing_mcps:
            confidence += 0.2

        # Lower confidence if we're missing MCPs
        if missing_mcps:
            confidence -= 0.1 * len(missing_mcps)

        return max(0.1, min(1.0, confidence))

    def get_missing_capabilities(self, intent: str) -> List[CapabilityMatch]:
        """Get list of MCPs that need to be installed for this intent."""
        analysis = self.analyze_intent(intent)
        return analysis.missing_mcps

    def suggest_installation(self, intent: str) -> List[Dict[str, str]]:
        """Suggest MCPs to install for an intent."""
        missing = self.get_missing_capabilities(intent)
        return [
            {
                "name": m.mcp_name,
                "install_command": m.install_command,
                "reason": f"Required for {m.capability}",
            }
            for m in missing
        ]

    def can_handle(self, intent: str) -> Tuple[bool, str]:
        """Check if we can handle this intent with current capabilities."""
        analysis = self.analyze_intent(intent)

        if analysis.required_mcps or not analysis.missing_mcps:
            return True, "All required capabilities available"

        if analysis.missing_mcps:
            missing_names = [m.mcp_name for m in analysis.missing_mcps]
            return False, f"Missing MCPs: {', '.join(missing_names)}"

        return True, "Can attempt with available capabilities"
