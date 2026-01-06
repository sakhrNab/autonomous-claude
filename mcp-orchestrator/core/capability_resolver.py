"""
Capability Resolver - The Self-Aware Brain

This module makes the Autonomous Operator truly intelligent by:
1. Discovering what MCPs are actually installed and available
2. Using the RIGHT tool for the job (Firecrawl for blocked sites, etc.)
3. Auto-installing missing capabilities when needed
4. Identifying gaps and implementing new features

This is NOT job-focused - it's a general-purpose capability resolver.
"""

import os
import json
import asyncio
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from mcp.registry import MCPRegistry, MCPCategory


@dataclass
class ResolvedCapability:
    """A capability that can be executed."""
    name: str
    mcp_name: Optional[str]
    method: str  # 'mcp', 'skill', 'claude_code', 'http'
    config: Dict[str, Any]
    priority: int  # Higher = try first


class CapabilityResolver:
    """
    The self-aware brain that figures out HOW to do things.

    Unlike the old pattern-matching approach, this:
    1. Actually queries installed MCPs
    2. Uses Claude Code for complex reasoning
    3. Falls back gracefully through multiple options
    4. Can implement new capabilities when needed
    """

    def __init__(self):
        self.registry = MCPRegistry()
        self.claude_cli = shutil.which("claude")
        self.project_root = Path(__file__).parent.parent

        # Cache of MCP capabilities discovered at runtime
        self._mcp_capabilities: Dict[str, List[str]] = {}
        self._last_discovery = None

    async def discover_installed_capabilities(self) -> Dict[str, Any]:
        """
        Discover what's actually installed and available.
        This is the KEY difference - we don't assume, we CHECK.
        """
        capabilities = {
            "mcps": {},
            "skills": {},
            "claude_code": self.claude_cli is not None,
            "discovered_at": datetime.now().isoformat(),
        }

        # Check each registered MCP
        for name in self.registry.list_all():
            if self.registry.is_installed(name):
                server = self.registry.get(name)
                if server:
                    capabilities["mcps"][name] = {
                        "category": server.category.value,
                        "capabilities": [c.name for c in server.capabilities],
                        "keywords": server.keywords,
                    }

        # Discover skills
        skills_path = self.project_root / "skills"
        if skills_path.exists():
            for skill_file in skills_path.glob("*.py"):
                if not skill_file.name.startswith("_"):
                    skill_name = skill_file.stem
                    capabilities["skills"][skill_name] = {
                        "path": str(skill_file),
                    }

        self._mcp_capabilities = capabilities["mcps"]
        self._last_discovery = datetime.now()

        return capabilities

    async def resolve_for_task(self, task_description: str, context: Dict[str, Any] = None) -> List[ResolvedCapability]:
        """
        Resolve capabilities needed for a task.

        Returns an ordered list of capabilities to try (highest priority first).
        """
        context = context or {}
        capabilities = []

        # Ensure we have fresh capability info
        if not self._last_discovery or (datetime.now() - self._last_discovery).seconds > 300:
            await self.discover_installed_capabilities()

        task_lower = task_description.lower()

        # ============================================
        # SCRAPING TASKS
        # ============================================
        if any(kw in task_lower for kw in ['scrape', 'extract', 'crawl', 'from', '.com', '.org', '.io', 'headline', 'content', 'page']):

            # 1. Firecrawl - best for blocked sites, JS-heavy sites (optional)
            if 'firecrawl' in self._mcp_capabilities:
                capabilities.append(ResolvedCapability(
                    name="firecrawl_scrape",
                    mcp_name="firecrawl",
                    method="mcp",
                    config={"tool": "firecrawl_scrape"},
                    priority=100,
                ))

            # 2. Universal Scraper skill (httpx + Claude analysis) - ALWAYS AVAILABLE
            capabilities.append(ResolvedCapability(
                name="universal_scraper",
                mcp_name=None,
                method="skill",
                config={"skill": "universal_scraper"},
                priority=80,  # High priority - this is the main fallback
            ))

            # 3. Direct HTTP fallback - ALWAYS AVAILABLE
            capabilities.append(ResolvedCapability(
                name="http_fetch",
                mcp_name=None,
                method="http",
                config={},
                priority=50,
            ))

            # NOTE: Playwright removed - doesn't work on Python 3.13 Windows

        # ============================================
        # SEARCH TASKS
        # ============================================
        elif any(kw in task_lower for kw in ['search', 'find', 'look up', 'what is', 'how to']):

            if 'brave-search' in self._mcp_capabilities:
                capabilities.append(ResolvedCapability(
                    name="brave_search",
                    mcp_name="brave-search",
                    method="mcp",
                    config={"tool": "brave_web_search"},
                    priority=100,
                ))

            if 'exa' in self._mcp_capabilities:
                capabilities.append(ResolvedCapability(
                    name="exa_search",
                    mcp_name="exa",
                    method="mcp",
                    config={"tool": "search"},
                    priority=90,
                ))

            # DuckDuckGo fallback
            capabilities.append(ResolvedCapability(
                name="duckduckgo_search",
                mcp_name=None,
                method="http",
                config={"provider": "duckduckgo"},
                priority=50,
            ))

        # ============================================
        # WORKFLOW/AUTOMATION TASKS
        # ============================================
        elif any(kw in task_lower for kw in ['automate', 'workflow', 'schedule', 'every day', 'recurring']):

            if 'n8n' in self._mcp_capabilities:
                capabilities.append(ResolvedCapability(
                    name="n8n_workflow",
                    mcp_name="n8n",
                    method="mcp",
                    config={"tool": "create_workflow"},
                    priority=100,
                ))

            if 'make' in self._mcp_capabilities:
                capabilities.append(ResolvedCapability(
                    name="make_scenario",
                    mcp_name="make",
                    method="mcp",
                    config={"tool": "run_scenario"},
                    priority=90,
                ))

        # ============================================
        # DATABASE TASKS
        # ============================================
        elif any(kw in task_lower for kw in ['database', 'sql', 'query', 'postgres', 'mysql']):

            if 'postgresql' in self._mcp_capabilities:
                capabilities.append(ResolvedCapability(
                    name="postgres_query",
                    mcp_name="postgresql",
                    method="mcp",
                    config={"tool": "query"},
                    priority=100,
                ))

        # ============================================
        # FILE TASKS
        # ============================================
        elif any(kw in task_lower for kw in ['file', 'read', 'write', 'create', 'directory']):

            if 'filesystem' in self._mcp_capabilities:
                capabilities.append(ResolvedCapability(
                    name="filesystem_op",
                    mcp_name="filesystem",
                    method="mcp",
                    config={"tool": "read_file"},
                    priority=100,
                ))

        # ============================================
        # CLAUDE CODE - Ultimate fallback for complex reasoning
        # ============================================
        if self.claude_cli:
            capabilities.append(ResolvedCapability(
                name="claude_code",
                mcp_name=None,
                method="claude_code",
                config={},
                priority=5,  # Low priority - use as last resort
            ))

        # Sort by priority (highest first)
        capabilities.sort(key=lambda c: c.priority, reverse=True)

        return capabilities

    async def execute_capability(
        self,
        capability: ResolvedCapability,
        task: str,
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Execute a resolved capability.

        Returns:
            {
                "success": bool,
                "data": Any,
                "error": Optional[str],
                "method_used": str,
            }
        """
        params = params or {}

        try:
            if capability.method == "mcp":
                return await self._execute_mcp(capability, task, params)
            elif capability.method == "skill":
                return await self._execute_skill(capability, task, params)
            elif capability.method == "http":
                return await self._execute_http(capability, task, params)
            elif capability.method == "claude_code":
                return await self._execute_claude_code(task, params)
            else:
                return {"success": False, "error": f"Unknown method: {capability.method}"}
        except Exception as e:
            return {"success": False, "error": str(e), "method_used": capability.method}

    async def _execute_mcp(
        self,
        capability: ResolvedCapability,
        task: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute via MCP server."""
        mcp_name = capability.mcp_name

        # Special handling for Firecrawl
        if mcp_name == "firecrawl":
            return await self._execute_firecrawl(task, params)

        # Special handling for Playwright
        if mcp_name == "playwright":
            return await self._execute_playwright(task, params)

        # Special handling for Brave Search
        if mcp_name == "brave-search":
            return await self._execute_brave_search(task, params)

        # Generic MCP execution would go through stdio/SSE
        # For now, return a placeholder
        return {
            "success": False,
            "error": f"Generic MCP execution not yet implemented for {mcp_name}",
            "method_used": "mcp",
        }

    async def _execute_brave_search(self, task: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute web search via Brave Search MCP.

        Requires BRAVE_API_KEY environment variable.
        Uses Claude Code CLI which has access to the Brave Search MCP.
        """
        import re

        # Extract search query from task
        query = params.get("query", "")
        if not query:
            # Extract from task description
            task_lower = task.lower()
            for prefix in ["search for", "search", "find", "look up", "execute:"]:
                if prefix in task_lower:
                    idx = task_lower.find(prefix)
                    query = task[idx + len(prefix):].strip()
                    break
            if not query:
                query = task

        print(f"[CapabilityResolver] Brave Search query: {query[:100]}")

        # Check if API key is configured
        api_key = os.environ.get("BRAVE_API_KEY")
        if not api_key:
            print("[CapabilityResolver] BRAVE_API_KEY not configured")
            return {
                "success": False,
                "error": "Brave Search requires BRAVE_API_KEY environment variable",
                "needs_api_key": True,
                "suggestion": "Set BRAVE_API_KEY in environment",
                "method_used": "brave_search",
            }

        # Use Brave Search API directly
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    headers={
                        "X-Subscription-Token": api_key,
                        "Accept": "application/json",
                    },
                    params={"q": query, "count": 10},
                    timeout=15.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    results = []

                    for item in data.get("web", {}).get("results", []):
                        results.append({
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "snippet": item.get("description", "")[:300],
                        })

                    if results:
                        print(f"[CapabilityResolver] Brave Search returned {len(results)} results")
                        return {
                            "success": True,
                            "data": {
                                "type": "search_results",
                                "query": query,
                                "results": results,
                                "count": len(results),
                            },
                            "method_used": "brave_search",
                        }
                    else:
                        return {
                            "success": False,
                            "error": "No results found",
                            "method_used": "brave_search",
                        }
                else:
                    return {
                        "success": False,
                        "error": f"Brave Search API error: {response.status_code}",
                        "method_used": "brave_search",
                    }

        except Exception as e:
            print(f"[CapabilityResolver] Brave Search error: {e}")
            return {
                "success": False,
                "error": str(e),
                "method_used": "brave_search",
            }

    async def _execute_firecrawl(self, task: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute scraping via Firecrawl.

        Firecrawl is OPEN SOURCE and can be:
        1. Self-hosted locally (no API key needed): docker run -p 3002:3002 mendableai/firecrawl
        2. Used via cloud API (needs FIRECRAWL_API_KEY)

        Excellent for:
        - Sites that block automation
        - JavaScript-heavy sites
        - Structured data extraction
        """
        import re
        import httpx

        # Extract URL from task
        url = params.get("url", "")
        if not url:
            url_match = re.search(r'https?://[^\s]+', task)
            if url_match:
                url = url_match.group(0)
            else:
                domain_match = re.search(r'(?:from\s+)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', task)
                if domain_match:
                    url = f"https://{domain_match.group(1)}"

        if not url:
            return {"success": False, "error": "Could not extract URL from task"}

        # Determine Firecrawl endpoint - local or cloud
        local_url = os.environ.get("FIRECRAWL_URL", "http://localhost:3002")
        api_key = os.environ.get("FIRECRAWL_API_KEY")

        # Try local Firecrawl first (self-hosted, no API key needed)
        async with httpx.AsyncClient() as client:
            # Try local instance first
            try:
                print(f"[CapabilityResolver] Trying local Firecrawl at {local_url}")
                response = await client.post(
                    f"{local_url}/v0/scrape",
                    headers={"Content-Type": "application/json"},
                    json={
                        "url": url,
                        "pageOptions": {"onlyMainContent": True},
                    },
                    timeout=60.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    print(f"[CapabilityResolver] Local Firecrawl success!")
                    return {
                        "success": True,
                        "data": data.get("data", {}),
                        "method_used": "firecrawl_local",
                        "url": url,
                    }
            except httpx.ConnectError:
                print(f"[CapabilityResolver] Local Firecrawl not running at {local_url}")
            except Exception as e:
                print(f"[CapabilityResolver] Local Firecrawl error: {e}")

            # Fall back to cloud API if local not available
            if api_key:
                try:
                    print("[CapabilityResolver] Trying Firecrawl cloud API")
                    response = await client.post(
                        "https://api.firecrawl.dev/v0/scrape",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "url": url,
                            "pageOptions": {"onlyMainContent": True},
                        },
                        timeout=60.0,
                    )

                    if response.status_code == 200:
                        data = response.json()
                        return {
                            "success": True,
                            "data": data.get("data", {}),
                            "method_used": "firecrawl_cloud",
                            "url": url,
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"Firecrawl cloud API error: {response.status_code}",
                            "response": response.text[:500],
                        }
                except Exception as e:
                    return {"success": False, "error": str(e), "method_used": "firecrawl_cloud"}

        # Neither local nor cloud available
        return {
            "success": False,
            "error": "Firecrawl not available",
            "suggestion": "Run locally: docker run -p 3002:3002 mendableai/firecrawl OR set FIRECRAWL_API_KEY",
            "needs_setup": True,
        }

    async def _execute_playwright(self, task: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Playwright is DISABLED on Python 3.13 Windows due to asyncio subprocess issues.
        Use Firecrawl or Universal Scraper instead.
        """
        return {
            "success": False,
            "error": "Playwright disabled (Python 3.13 asyncio issue). Use Firecrawl or Universal Scraper.",
            "method_used": "playwright",
        }

    async def _execute_skill(
        self,
        capability: ResolvedCapability,
        task: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a local skill."""
        skill_name = capability.config.get("skill", "")

        if skill_name == "universal_scraper":
            from skills.universal_scraper import get_universal_scraper
            scraper = await get_universal_scraper()

            # Extract URL and query from task
            import re
            url = params.get("url", "")
            query = params.get("query", "")

            if not url:
                url_match = re.search(r'https?://[^\s]+', task)
                if url_match:
                    url = url_match.group(0)
                else:
                    domain_match = re.search(r'(?:from\s+)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', task)
                    if domain_match:
                        url = f"https://{domain_match.group(1)}"

            result = await scraper.scrape_intelligent(
                url=url,
                user_intent=task,
                requested_fields=params.get("fields", [])
            )

            return {
                "success": result.get("success", False),
                "data": result,
                "method_used": "universal_scraper",
            }

        return {"success": False, "error": f"Unknown skill: {skill_name}"}

    async def _execute_http(
        self,
        capability: ResolvedCapability,
        task: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute direct HTTP request or search."""
        import httpx
        import re
        import urllib.parse
        import html as html_module

        # Check if this is a search request
        provider = capability.config.get("provider", "")
        if provider == "duckduckgo" or capability.name == "duckduckgo_search":
            return await self._execute_duckduckgo_search(task, params)

        url = params.get("url", "")
        if not url:
            url_match = re.search(r'https?://[^\s]+', task)
            if url_match:
                url = url_match.group(0)

        if not url:
            return {"success": False, "error": "No URL found"}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=30.0,
                    follow_redirects=True,
                )

                return {
                    "success": True,
                    "data": {
                        "url": url,
                        "status_code": response.status_code,
                        "content": response.text[:10000],
                        "content_type": response.headers.get("content-type", ""),
                    },
                    "method_used": "http",
                }
        except Exception as e:
            return {"success": False, "error": str(e), "method_used": "http"}

    async def _execute_duckduckgo_search(self, task: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute web search via DuckDuckGo HTML (no API key needed)."""
        import httpx
        import re
        import urllib.parse
        import html as html_module

        # Extract search query from task
        query = params.get("query", "")
        if not query:
            # Try to extract meaningful query from task
            task_lower = task.lower()
            # Remove common prefixes
            for prefix in ["find", "search for", "search", "look up", "get", "execute:"]:
                if task_lower.startswith(prefix):
                    query = task[len(prefix):].strip()
                    break
            if not query:
                query = task

        print(f"[CapabilityResolver] DuckDuckGo search: {query[:100]}")

        try:
            encoded_query = urllib.parse.quote_plus(query)
            url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    },
                    timeout=15.0,
                )

            html = response.text

            # Check for bot detection
            if "anomaly" in html.lower() or "botnet" in html.lower() or "challenge" in html.lower():
                print("[CapabilityResolver] DuckDuckGo blocked (bot detection)")
                return {
                    "success": False,
                    "error": "DuckDuckGo blocked - bot detection",
                    "method_used": "duckduckgo_search",
                }

            results = []

            # Extract results from DuckDuckGo HTML
            result_pattern = r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>([^<]*)</a>'
            snippet_pattern = r'<a[^>]*class="result__snippet"[^>]*>([^<]*(?:<[^>]*>[^<]*)*)</a>'

            links = re.findall(result_pattern, html)
            snippets = re.findall(snippet_pattern, html)

            for i, (link, title) in enumerate(links[:10]):
                snippet = snippets[i] if i < len(snippets) else ""
                snippet = re.sub(r'<[^>]+>', '', snippet).strip()
                snippet = html_module.unescape(snippet)

                # Extract actual URL from DuckDuckGo redirect
                actual_url = link
                if 'uddg=' in link:
                    url_match = re.search(r'uddg=([^&]+)', link)
                    if url_match:
                        actual_url = urllib.parse.unquote(url_match.group(1))

                results.append({
                    "title": html_module.unescape(title.strip()),
                    "url": actual_url,
                    "snippet": snippet[:300],
                })

            if results:
                return {
                    "success": True,
                    "data": {
                        "type": "search_results",
                        "query": query,
                        "results": results,
                        "count": len(results),
                    },
                    "method_used": "duckduckgo_search",
                }
            else:
                return {"success": False, "error": "No search results found", "method_used": "duckduckgo_search"}

        except Exception as e:
            return {"success": False, "error": str(e), "method_used": "duckduckgo_search"}

    async def _execute_claude_code(self, task: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute via Claude Code CLI for complex reasoning."""
        if not self.claude_cli:
            return {"success": False, "error": "Claude Code CLI not available"}

        try:
            prompt = f"""Execute this task autonomously:

{task}

Use all available tools to accomplish this. If you need to scrape a website,
install MCPs, or write code - do it. Return a structured result."""

            process = await asyncio.create_subprocess_exec(
                self.claude_cli,
                "-p", prompt,
                "--output-format", "text",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.project_root),
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
            output = stdout.decode("utf-8").strip()

            return {
                "success": process.returncode == 0,
                "data": {"output": output},
                "method_used": "claude_code",
            }
        except asyncio.TimeoutError:
            return {"success": False, "error": "Claude Code timed out", "method_used": "claude_code"}
        except Exception as e:
            return {"success": False, "error": str(e), "method_used": "claude_code"}

    async def identify_missing_capability(self, task: str, errors: List[str]) -> Optional[Dict[str, Any]]:
        """
        Identify what capability is missing and how to implement it.

        This is the SELF-HEALING part - when something fails, we figure out
        what's missing and how to add it.
        """
        if not self.claude_cli:
            return None

        prompt = f"""Analyze this failed task and identify what capability is missing:

TASK: {task}

ERRORS:
{chr(10).join(errors)}

AVAILABLE MCPS: {list(self._mcp_capabilities.keys())}

Respond with JSON:
{{
    "missing_capability": "what's missing",
    "solution_type": "install_mcp" | "implement_skill" | "configure_api_key" | "other",
    "solution": {{
        "mcp_name": "if install_mcp",
        "install_command": "command to run",
        "env_var": "if api key needed",
        "implementation_hint": "if implement_skill"
    }},
    "can_auto_fix": true/false
}}"""

        try:
            process = await asyncio.create_subprocess_exec(
                self.claude_cli,
                "-p", prompt,
                "--output-format", "text",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=30)
            output = stdout.decode("utf-8").strip()

            # Try to parse JSON from output
            import re
            json_match = re.search(r'\{[^{}]*\}', output, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception:
            pass

        return None

    async def auto_install_mcp(self, mcp_name: str) -> Dict[str, Any]:
        """Auto-install an MCP if user has given permission."""
        server = self.registry.get(mcp_name)
        if not server:
            return {"success": False, "error": f"Unknown MCP: {mcp_name}"}

        try:
            process = await asyncio.create_subprocess_shell(
                server.install_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)

            if process.returncode == 0:
                self.registry.mark_installed(mcp_name)
                return {
                    "success": True,
                    "message": f"Installed {mcp_name}",
                    "output": stdout.decode()[:500],
                }
            else:
                return {
                    "success": False,
                    "error": stderr.decode()[:500],
                }
        except Exception as e:
            return {"success": False, "error": str(e)}


# Singleton
_resolver: Optional[CapabilityResolver] = None


def get_capability_resolver() -> CapabilityResolver:
    """Get the singleton capability resolver."""
    global _resolver
    if _resolver is None:
        _resolver = CapabilityResolver()
    return _resolver


async def resolve_and_execute(task: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Main entry point - resolve capabilities and execute the task.

    Tries each capability in order until one succeeds.
    """
    resolver = get_capability_resolver()
    params = params or {}

    # Get ordered list of capabilities to try
    capabilities = await resolver.resolve_for_task(task, params)

    if not capabilities:
        return {
            "success": False,
            "error": "No capabilities available for this task",
            "suggestion": "Try installing relevant MCPs",
        }

    errors = []
    needs_config = []

    for capability in capabilities:
        print(f"[CapabilityResolver] Trying {capability.name} (priority: {capability.priority})")

        result = await resolver.execute_capability(capability, task, params)

        if result.get("success"):
            result["capability_used"] = capability.name
            return result
        else:
            error = result.get('error', 'Unknown error')
            errors.append(f"{capability.name}: {error}")

            # Track what needs configuration
            if result.get("needs_api_key"):
                needs_config.append({
                    "capability": capability.name,
                    "issue": "needs_api_key",
                    "suggestion": result.get("suggestion", ""),
                })

    # All capabilities failed - try to identify what's missing
    missing = await resolver.identify_missing_capability(task, errors)

    # Build helpful suggestion
    suggestion = ""
    if needs_config:
        suggestion = f"Configure: {needs_config[0]['suggestion']}"
    elif missing:
        suggestion = missing.get("solution", "Check logs for details")
    else:
        suggestion = "Check logs for details"

    return {
        "success": False,
        "error": "All capabilities failed",
        "errors": errors,
        "missing_capability": missing,
        "needs_configuration": needs_config,
        "suggestion": suggestion,
    }
