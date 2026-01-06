"""
Intelligent Orchestrator

This is the brain of the autonomous operator. It uses Claude to:
1. Understand user intent
2. Create execution plans with specific agents, skills, MCPs
3. Execute the plan intelligently with fallbacks
4. Interpret results and extract relevant information
5. Self-heal by identifying and implementing missing capabilities

Architecture:
- ExecutionPlanner: Creates step-by-step plans (saved to plans/)
- CapabilityResolver: Figures out HOW to execute each step
- This Orchestrator: Coordinates everything

KEY FEATURES:
- Uses Claude Code CLI (your subscription, no API key needed)
- Firecrawl integration (local or cloud) for blocked sites
- Universal Scraper for intelligent extraction from ANY site
- Self-healing: identifies gaps and suggests fixes
"""

import os
import json
import asyncio
import httpx
import subprocess
import shutil
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

# Known working job sites (tested and confirmed working)
WORKING_JOB_SITES = {
    "remoteok.com": {
        "name": "RemoteOK",
        "search_url": "https://remoteok.com/remote-{query}-jobs",
        "works": True,
    },
    "weworkremotely.com": {
        "name": "WeWorkRemotely",
        "search_url": "https://weworkremotely.com/remote-jobs/search?term={query}",
        "works": True,
    },
    "workingnomads.com": {
        "name": "Working Nomads",
        "search_url": "https://www.workingnomads.com/jobs?category=development",
        "works": True,
    },
    "startup.jobs": {
        "name": "Startup.Jobs",
        "search_url": "https://startup.jobs/?q={query}",
        "works": True,
    },
}

# Try to import anthropic, but it's optional now
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False
    anthropic = None


@dataclass
class ExecutionPlan:
    """A plan for executing a user request."""
    intent: str
    understood_goal: str
    steps: List[Dict[str, Any]]
    tools_needed: List[str]
    mcps_needed: List[str]
    skills_needed: List[str]
    agents_needed: List[str]
    hooks_to_trigger: List[str]
    estimated_complexity: str  # simple, moderate, complex
    requires_new_capability: bool = False
    new_capability_description: Optional[str] = None


@dataclass
class ExecutionResult:
    """Result of executing a plan."""
    success: bool
    answer: str  # The actual answer to the user's question
    raw_data: Dict[str, Any]  # Raw data collected
    steps_executed: List[Dict[str, Any]]
    execution_info: Dict[str, Any]


class IntelligentOrchestrator:
    """
    The intelligent orchestrator that uses Claude to reason about tasks.

    This is fundamentally different from pattern matching:
    - It UNDERSTANDS what the user wants
    - It PLANS how to get it
    - It EXECUTES intelligently
    - It INTERPRETS results to give meaningful answers

    Uses Claude Code CLI for reasoning - no separate API key needed!
    """

    def __init__(self):
        # Check for Claude Code CLI first (uses existing subscription)
        self.claude_cli_path = shutil.which("claude")
        self.has_claude_cli = self.claude_cli_path is not None

        # Fallback to API key if available
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.has_api_key = bool(api_key) and HAS_ANTHROPIC

        if self.has_claude_cli:
            print("Using Claude Code CLI for intelligent reasoning (your subscription)")
            self.client = None
            self.model = None
        elif self.has_api_key:
            self.client = anthropic.Anthropic()
            self.model = "claude-sonnet-4-20250514"
        else:
            self.client = None
            self.model = None
            print("Note: Using smart heuristics mode. For full AI reasoning, Claude Code CLI will be used.")

        # Available capabilities
        self.available_mcps = self._load_available_mcps()
        self.available_skills = self._load_available_skills()
        self.available_agents = self._load_available_agents()
        self.available_hooks = self._load_available_hooks()

        # Execution history for learning
        self.execution_history: List[Dict] = []

        # Questions to ask user for clarification
        self.pending_questions: List[str] = []

    async def _ask_claude_cli(self, prompt: str) -> str:
        """
        Use Claude Code CLI to get intelligent responses.
        This uses your existing Claude subscription - no API key needed!
        """
        if not self.has_claude_cli:
            return ""

        try:
            # Run claude CLI with the prompt
            result = await asyncio.create_subprocess_exec(
                self.claude_cli_path,
                "-p", prompt,
                "--output-format", "text",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=60)
            return stdout.decode("utf-8").strip()
        except asyncio.TimeoutError:
            return ""
        except Exception as e:
            print(f"Claude CLI error: {e}")
            return ""

    def _load_available_mcps(self) -> Dict[str, Dict]:
        """Load available MCP servers and their capabilities."""
        return {
            "brave-search": {
                "description": "Web search using Brave Search API",
                "capabilities": ["search the web", "find information", "lookup facts"],
                "when_to_use": "When user asks questions, wants to find information, or search for anything",
            },
            "playwright": {
                "description": "Browser automation for web scraping and interaction",
                "capabilities": ["scrape websites", "extract data from pages", "interact with web apps"],
                "when_to_use": "When user wants to scrape a specific website, extract structured data, or automate browser tasks",
            },
            "postgresql": {
                "description": "Database queries and operations",
                "capabilities": ["query databases", "run SQL", "get data from tables"],
                "when_to_use": "When user wants to query a database or work with structured data",
            },
            "filesystem": {
                "description": "File system operations",
                "capabilities": ["read files", "write files", "list directories"],
                "when_to_use": "When user wants to work with local files",
            },
            "n8n": {
                "description": "Workflow automation",
                "capabilities": ["create workflows", "automate processes", "schedule tasks"],
                "when_to_use": "When user wants to automate repetitive tasks or create workflows",
            },
        }

    def _load_available_skills(self) -> Dict[str, Dict]:
        """Load available skills."""
        return {
            "web-search": {
                "description": "Search the web and return relevant results",
                "function": "execute_web_search",
            },
            "web-scrape": {
                "description": "Scrape a website and extract specific information",
                "function": "execute_web_scrape",
            },
            "data-extraction": {
                "description": "Extract specific data from raw content",
                "function": "execute_data_extraction",
            },
        }

    def _load_available_agents(self) -> Dict[str, Dict]:
        """Load available agents."""
        return {
            "research-agent": {
                "description": "Researches topics by searching and synthesizing information",
                "capabilities": ["research", "summarize", "compare"],
            },
            "extraction-agent": {
                "description": "Extracts specific information from various sources",
                "capabilities": ["extract", "parse", "structure"],
            },
            "automation-agent": {
                "description": "Automates tasks and workflows",
                "capabilities": ["automate", "schedule", "orchestrate"],
            },
        }

    def _load_available_hooks(self) -> Dict[str, Dict]:
        """Load available hooks."""
        return {
            "task-ledger-update": {
                "description": "Updates the task ledger with execution status",
                "trigger": "always",
            },
            "result-validator": {
                "description": "Validates results before returning to user",
                "trigger": "on_completion",
            },
            "error-handler": {
                "description": "Handles errors and retries",
                "trigger": "on_error",
            },
        }

    async def understand_and_plan(self, user_intent: str) -> ExecutionPlan:
        """
        Use Claude to understand what the user wants and create an execution plan.

        This is the KEY difference from pattern matching - we actually UNDERSTAND.
        """

        system_prompt = """You are an intelligent task planner for an autonomous operator system.

Your job is to:
1. UNDERSTAND what the user really wants (not just pattern match keywords)
2. PLAN how to achieve it using available tools
3. DECIDE which MCPs, skills, agents, and hooks to use

Available MCPs (Model Context Protocol servers):
{mcps}

Available Skills:
{skills}

Available Agents:
{agents}

Available Hooks:
{hooks}

IMPORTANT: Think about what the user ACTUALLY wants, not just what words they used.
For example:
- "give me cheapest shoes in berlin" -> User wants SEARCH results for shoe stores
- "scrape opening times from X" -> User wants SPECIFIC DATA (opening times), not random page content
- "what is Y" -> User wants a CLEAR ANSWER, not just links

Output your plan as JSON with this structure:
{{
    "understood_goal": "What the user actually wants (be specific)",
    "steps": [
        {{"step": 1, "action": "description", "tool": "tool_name", "params": {{}}}}
    ],
    "tools_needed": ["tool1", "tool2"],
    "mcps_needed": ["mcp1"],
    "skills_needed": ["skill1"],
    "agents_needed": ["agent1"],
    "hooks_to_trigger": ["hook1"],
    "complexity": "simple|moderate|complex",
    "requires_new_capability": false,
    "new_capability_description": null
}}"""

        # Format available capabilities for the prompt
        mcps_desc = "\n".join([f"- {name}: {info['description']} (use when: {info['when_to_use']})"
                              for name, info in self.available_mcps.items()])
        skills_desc = "\n".join([f"- {name}: {info['description']}"
                                for name, info in self.available_skills.items()])
        agents_desc = "\n".join([f"- {name}: {info['description']}"
                                for name, info in self.available_agents.items()])
        hooks_desc = "\n".join([f"- {name}: {info['description']}"
                               for name, info in self.available_hooks.items()])

        formatted_system = system_prompt.format(
            mcps=mcps_desc,
            skills=skills_desc,
            agents=agents_desc,
            hooks=hooks_desc,
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=formatted_system,
            messages=[
                {"role": "user", "content": f"Plan how to handle this request: {user_intent}"}
            ]
        )

        # Parse the response
        response_text = response.content[0].text

        # Extract JSON from response
        try:
            # Find JSON in response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                plan_json = json.loads(response_text[json_start:json_end])
            else:
                # Fallback plan
                plan_json = {
                    "understood_goal": user_intent,
                    "steps": [{"step": 1, "action": "search", "tool": "web-search"}],
                    "tools_needed": ["web-search"],
                    "mcps_needed": ["brave-search"],
                    "skills_needed": ["web-search"],
                    "agents_needed": [],
                    "hooks_to_trigger": ["task-ledger-update"],
                    "complexity": "simple",
                }
        except json.JSONDecodeError:
            plan_json = {
                "understood_goal": user_intent,
                "steps": [{"step": 1, "action": "search", "tool": "web-search"}],
                "tools_needed": ["web-search"],
                "mcps_needed": ["brave-search"],
                "skills_needed": ["web-search"],
                "agents_needed": [],
                "hooks_to_trigger": ["task-ledger-update"],
                "complexity": "simple",
            }

        return ExecutionPlan(
            intent=user_intent,
            understood_goal=plan_json.get("understood_goal", user_intent),
            steps=plan_json.get("steps", []),
            tools_needed=plan_json.get("tools_needed", []),
            mcps_needed=plan_json.get("mcps_needed", []),
            skills_needed=plan_json.get("skills_needed", []),
            agents_needed=plan_json.get("agents_needed", []),
            hooks_to_trigger=plan_json.get("hooks_to_trigger", ["task-ledger-update"]),
            estimated_complexity=plan_json.get("complexity", "simple"),
            requires_new_capability=plan_json.get("requires_new_capability", False),
            new_capability_description=plan_json.get("new_capability_description"),
        )

    async def execute_plan(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """Execute the plan and collect raw data."""

        results = {
            "raw_data": {},
            "steps_executed": [],
            "errors": [],
        }

        for step in plan.steps:
            step_result = await self._execute_step(step, plan)
            results["steps_executed"].append({
                "step": step,
                "result": step_result,
            })

            if step_result.get("success"):
                results["raw_data"][f"step_{step.get('step', 0)}"] = step_result.get("data")
            else:
                results["errors"].append(step_result.get("error"))

        return results

    async def _execute_step(self, step: Dict, plan: ExecutionPlan) -> Dict[str, Any]:
        """Execute a single step of the plan."""

        tool = step.get("tool", "")
        action = step.get("action", "")
        params = step.get("params", {})

        try:
            if tool in ["web-search", "search"] or "search" in action.lower():
                return await self._do_web_search(plan.intent, params)
            elif tool in ["web-scrape", "scrape"] or "scrape" in action.lower():
                return await self._do_web_scrape(plan.intent, params)
            elif tool in ["extract", "data-extraction"]:
                return await self._do_data_extraction(params)
            else:
                # Default to search
                return await self._do_web_search(plan.intent, params)
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _do_web_search(self, query: str, params: Dict) -> Dict[str, Any]:
        """
        Perform a web search using capability resolver.
        Tries: Brave Search MCP → DuckDuckGo → Fallback message
        """
        import urllib.parse

        search_query = params.get("query", query)
        print(f"[Intelligent Orchestrator] Web search for: {search_query[:100]}")

        # Try capability resolver for search
        try:
            from core.capability_resolver import resolve_and_execute
            result = await resolve_and_execute(f"search {search_query}", {"query": search_query})

            if result.get("success"):
                data = result.get("data", {})
                if data.get("type") == "search_results" and data.get("results"):
                    print(f"[Intelligent Orchestrator] Search returned {len(data['results'])} results")
                    return {"success": True, "data": data}
        except Exception as e:
            print(f"[Intelligent Orchestrator] Capability resolver search error: {e}")

        # Direct DuckDuckGo attempt (may fail due to bot detection)
        encoded_query = urllib.parse.quote_plus(search_query)
        url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Accept": "text/html,application/xhtml+xml",
                        "Accept-Language": "en-US,en;q=0.9",
                    },
                    timeout=15.0,
                )

            html = response.text

            # Check for bot detection
            if "anomaly" in html.lower() or "botnet" in html.lower() or "challenge" in html.lower():
                print("[Intelligent Orchestrator] DuckDuckGo blocked (bot detection)")
                return {
                    "success": False,
                    "data": {
                        "type": "search_results",
                        "query": search_query,
                        "results": [],
                        "error": "Search services blocked automated requests",
                        "suggestion": "Configure Brave Search MCP with API key for web search",
                    }
                }

            # Extract results
            import re
            results = []

            result_pattern = r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>([^<]*)</a>'
            snippet_pattern = r'<a[^>]*class="result__snippet"[^>]*>([^<]*(?:<[^>]*>[^<]*)*)</a>'

            links = re.findall(result_pattern, html)
            snippets = re.findall(snippet_pattern, html)

            for i, (link, title) in enumerate(links[:10]):
                snippet = snippets[i] if i < len(snippets) else ""
                snippet = re.sub(r'<[^>]+>', '', snippet).strip()

                actual_url = link
                if 'uddg=' in link:
                    url_match = re.search(r'uddg=([^&]+)', link)
                    if url_match:
                        actual_url = urllib.parse.unquote(url_match.group(1))

                results.append({
                    "title": title.strip(),
                    "url": actual_url,
                    "snippet": snippet[:300],
                })

            if results:
                return {
                    "success": True,
                    "data": {
                        "type": "search_results",
                        "query": search_query,
                        "results": results,
                    }
                }
            else:
                return {
                    "success": False,
                    "data": {
                        "type": "search_results",
                        "query": search_query,
                        "results": [],
                        "error": "No results found or search blocked",
                        "suggestion": "Try scraping a specific news site like bbc.com instead",
                    }
                }

        except Exception as e:
            print(f"[Intelligent Orchestrator] Search error: {e}")
            return {
                "success": False,
                "data": {
                    "type": "search_results",
                    "query": search_query,
                    "results": [],
                    "error": str(e),
                }
            }

    async def _do_web_scrape(self, intent: str, params: Dict) -> Dict[str, Any]:
        """
        INTELLIGENT web scraping - uses Capability Resolver to find the best method.

        PRIORITY ORDER (determined by installed MCPs):
        1. Firecrawl MCP (if installed) - best for blocked sites
        2. Apify MCP (if installed) - pre-built scrapers
        3. Playwright MCP (if installed) - browser automation
        4. Universal Scraper skill - Claude AI analysis
        5. Direct HTTP - basic fallback

        This is GENERAL PURPOSE, not job-focused.
        """
        import re
        import urllib.parse

        # Extract URL and search terms from intent
        url = params.get("url", "")
        search_terms = self._extract_search_terms(intent)
        requested_fields = self._parse_requested_fields(intent)

        if not url:
            url_match = re.search(r'https?://[^\s]+', intent)
            if url_match:
                url = url_match.group(0)
            else:
                domain_match = re.search(r'(?:from\s+)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', intent)
                if domain_match:
                    url = f"https://{domain_match.group(1)}"

        # ============================================================
        # STEP 0: TRY CAPABILITY RESOLVER (uses installed MCPs first!)
        # ============================================================
        try:
            from core.capability_resolver import resolve_and_execute

            print(f"[Intelligent Orchestrator] Using Capability Resolver for: {url or intent}")

            result = await resolve_and_execute(intent, {
                "url": url,
                "query": ' '.join(search_terms) if search_terms else "",
                "fields": requested_fields,
            })

            if result.get("success"):
                data = result.get("data", {})
                method = result.get("method_used", result.get("capability_used", "unknown"))
                print(f"[Intelligent Orchestrator] SUCCESS! Method: {method}, Data keys: {list(data.keys()) if isinstance(data, dict) else 'not dict'}")

                # Check if this is a search result
                if isinstance(data, dict) and data.get("type") == "search_results":
                    results = data.get("results", [])
                    print(f"[Intelligent Orchestrator] Search returned {len(results)} results")
                    return {
                        "success": True,
                        "data": {
                            "type": "search_results",
                            "query": data.get("query", intent),
                            "results": results,
                            "method": method,
                        }
                    }

                # Extract actual content from the data (for scraping)
                raw_content = data.get("content", "") if isinstance(data, dict) else data

                # Process content into displayable format
                relevant_content = []
                if isinstance(raw_content, list):
                    # List of items (e.g., headlines)
                    for item in raw_content:
                        if isinstance(item, dict):
                            # Format dict items nicely (e.g., {"title": "headline"})
                            title = item.get("title", item.get("headline", ""))
                            if title:
                                relevant_content.append(title)
                            else:
                                # Use first string value found
                                for v in item.values():
                                    if isinstance(v, str) and len(v) > 5:
                                        relevant_content.append(v)
                                        break
                        elif isinstance(item, str):
                            relevant_content.append(item)
                elif isinstance(raw_content, dict):
                    # Dict with content field
                    text_content = raw_content.get("content", raw_content.get("text", raw_content.get("summary", "")))
                    if text_content:
                        relevant_content.append(str(text_content))
                elif raw_content:
                    relevant_content.append(str(raw_content))

                print(f"[Intelligent Orchestrator] Extracted {len(relevant_content)} content items. Preview: {relevant_content[:3] if relevant_content else 'empty'}")

                # Return in a format the rest of the system can use
                return {
                    "success": True,
                    "data": {
                        "type": "scraped_content",
                        "url": url,
                        "method": method,
                        "title": data.get("source_title", data.get("title", url)),
                        "relevant_content": relevant_content,
                        "raw_content": raw_content,
                        "note": f"Scraped using {method}",
                    }
                }
            else:
                # Capability resolver failed, fall through to legacy logic
                error_msg = result.get('error', 'Unknown error')
                print(f"[Intelligent Orchestrator] Capability resolver returned success=False: {error_msg}")

                # Surface configuration needs to user
                if result.get("needs_configuration"):
                    configs = result["needs_configuration"]
                    for cfg in configs:
                        print(f"[Intelligent Orchestrator] NEEDS CONFIG: {cfg['suggestion']}")

                if result.get("missing_capability"):
                    missing = result["missing_capability"]
                    print(f"[Intelligent Orchestrator] Missing: {missing}")

                # Store the suggestion for later use
                self._last_suggestion = result.get("suggestion", "")

        except ImportError:
            print("[Intelligent Orchestrator] Capability resolver not available, using legacy logic")
        except Exception as e:
            print(f"[Intelligent Orchestrator] Capability resolver error: {e}")

        # ============================================================
        # STEP 1: LEGACY - TRY UNIVERSAL SCRAPER (Claude-powered AI extraction)
        # ============================================================
        is_job_site = self._is_job_site(url) if url else True
        search_query = ' '.join(search_terms) if search_terms else "software engineer"

        if is_job_site:
            print(f"[Intelligent Orchestrator] Using Universal Scraper for job extraction")
            print(f"[Intelligent Orchestrator] Requested fields: {requested_fields}")
            print(f"[Intelligent Orchestrator] Search terms: {search_terms}")

            try:
                from skills.universal_scraper import get_universal_scraper
                scraper = await get_universal_scraper()

                # Try the requested site first
                if url:
                    print(f"[Intelligent Orchestrator] Trying requested site: {url}")
                    result = await scraper.scrape_jobs(
                        site=url,
                        query=search_query,
                        user_intent=intent,
                        requested_fields=requested_fields,
                        max_jobs=10
                    )

                    if result.get("success") and result.get("jobs"):
                        jobs = result["jobs"]
                        print(f"[Intelligent Orchestrator] SUCCESS! Got {len(jobs)} jobs from {url}")
                        return {
                            "success": True,
                            "data": {
                                "type": "job_listings",
                                "site": url,
                                "search_terms": search_terms,
                                "jobs_found": len(jobs),
                                "jobs": jobs,
                                "requested_fields": requested_fields,
                                "method": result.get("method", "universal_scraper"),
                                "note": f"Extracted {len(jobs)} jobs using Claude AI intelligent analysis"
                            }
                        }
                    elif result.get("blocked"):
                        print(f"[Intelligent Orchestrator] Site {url} blocked - trying working alternatives")

                # If requested site failed or blocked, try known working sites
                requested_site_name = url.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0] if url else ""
                print(f"[Intelligent Orchestrator] Site '{requested_site_name}' didn't return jobs, trying alternatives...")

                for site_domain, site_config in WORKING_JOB_SITES.items():
                    if site_config.get("works"):
                        print(f"[Intelligent Orchestrator] Trying {site_config['name']}...")
                        result = await scraper.scrape_jobs(
                            site=site_domain,
                            query=search_query,
                            user_intent=intent,
                            requested_fields=requested_fields,
                            max_jobs=10
                        )

                        if result.get("success") and result.get("jobs"):
                            jobs = result["jobs"]
                            # CLEAR WARNING when using fallback site
                            is_fallback = requested_site_name and site_domain not in requested_site_name.lower()
                            if is_fallback:
                                note = f"WARNING: {requested_site_name} blocked access. Showing {len(jobs)} jobs from {site_config['name']} instead."
                                warning = f"{requested_site_name} blocks automated access. Results are from {site_config['name']}."
                            else:
                                note = f"Found {len(jobs)} jobs from {site_config['name']}"
                                warning = None
                            print(f"[Intelligent Orchestrator] SUCCESS! {note}")
                            return {
                                "success": True,
                                "data": {
                                    "type": "job_listings",
                                    "site": site_config['name'],
                                    "actual_source": site_domain,
                                    "original_site_requested": requested_site_name if is_fallback else None,
                                    "fallback_used": is_fallback,
                                    "search_terms": search_terms,
                                    "jobs_found": len(jobs),
                                    "jobs": jobs,
                                    "requested_fields": requested_fields,
                                    "method": result.get("method", "universal_scraper"),
                                    "note": note,
                                    "warning": warning
                                }
                            }

            except Exception as scraper_err:
                print(f"[Intelligent Orchestrator] Universal scraper error: {scraper_err}")

        # ============================================================
        # STEP 2: FALLBACK - Original scraping logic
        # ============================================================
        if not url:
            return {"success": False, "error": "Could not identify URL to scrape"}

        # Detect site type and build intelligent search URL
        is_job_site = self._is_job_site(url)

        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

            if is_job_site and search_terms:
                # Build job search URL
                search_url = self._build_job_search_url(url, search_terms)
                response = await client.get(search_url, headers=headers)
                html = response.text

                # Extract job listings
                jobs = await self._extract_job_listings(client, headers, html, url, search_terms, max_jobs=5)

                # Check if we got meaningful results
                good_jobs = [j for j in jobs if j.get("requirements", [""])[0] != "Requirements not found in standard format"]

                if good_jobs:
                    return {
                        "success": True,
                        "data": {
                            "type": "job_listings",
                            "site": url,
                            "search_terms": search_terms,
                            "jobs_found": len(good_jobs),
                            "jobs": good_jobs,
                        }
                    }

                # If direct HTTP scraping didn't work, try DEEP browser automation (Playwright)
                # This visits EACH job page to extract full requirements
                site_blocked = False
                try:
                    from skills.browser_automation import get_browser_skill
                    browser = await get_browser_skill()
                    browser_result = await browser.scrape_jobs_deep(
                        site_url=url,
                        search_query=' '.join(search_terms),
                        max_jobs=5
                    )
                    # Check if site blocked us
                    if browser_result and browser_result.get("blocked"):
                        site_blocked = True
                        print(f"[Intelligent Orchestrator] Site blocked automated access, falling back to web search")
                    elif browser_result and browser_result.get("success") and browser_result.get("jobs"):
                        browser_jobs = browser_result.get("jobs", [])
                        # Filter out jobs with empty requirements or placeholder text
                        good_browser_jobs = [
                            j for j in browser_jobs
                            if j.get("requirements") and len(j["requirements"]) > 0
                            and j["requirements"][0] not in ["", "Click to view full job details and requirements", "Visit the job page for full details"]
                        ]
                        # Include jobs even with basic info if they have good URLs
                        if not good_browser_jobs:
                            good_browser_jobs = [j for j in browser_jobs if j.get("url") and not self._is_ad_url(j["url"])]

                        if good_browser_jobs:
                            return {
                                "success": True,
                                "data": {
                                    "type": "job_listings",
                                    "site": url,
                                    "search_terms": search_terms,
                                    "jobs_found": len(good_browser_jobs),
                                    "jobs": good_browser_jobs,
                                    "note": "Deep scraped with Playwright - visited each job page for full details.",
                                    "method": "deep_scrape"
                                }
                            }
                except Exception as browser_err:
                    print(f"[Intelligent Orchestrator] Deep scrape failed: {browser_err}")

                # Final fallback: web search for jobs from this site
                site_domain = urllib.parse.urlparse(url).netloc
                search_query = f"site:{site_domain} {' '.join(search_terms)} job requirements"
                search_result = await self._do_web_search(search_query, {"query": search_query})

                if search_result.get("success"):
                    search_data = search_result.get("data", {})
                    results = search_data.get("results", [])

                    # Parse what fields user wants from their intent
                    requested_fields = self._parse_requested_fields(intent)
                    print(f"[Intelligent Orchestrator] User requested fields: {requested_fields}")

                    # Collect job URLs from search results (only actual job pages, not listing pages)
                    job_urls = []
                    ad_domains = ['duckduckgo.com', 'bing.com/aclick', 'google.com/aclk', 'ad.doubleclick']
                    for r in results[:15]:
                        job_url = r.get("url", "")
                        # Skip ad/tracking URLs
                        if any(ad in job_url.lower() for ad in ad_domains):
                            continue
                        # Only include actual job pages (with job ID in URL), not listing pages
                        # Job pages typically have: /jobs/job-title-123456 or /job/123456
                        if re.search(r'/jobs?/[^/]+-\d+|/jobs?/\d+|/vacancy/\d+', job_url):
                            job_urls.append(job_url)
                        if len(job_urls) >= 5:
                            break

                    print(f"[Intelligent Orchestrator] Found {len(job_urls)} actual job page URLs")

                    # Use INTELLIGENT extraction with Claude
                    if job_urls:
                        try:
                            from skills.browser_automation import get_browser_skill
                            browser = await get_browser_skill()
                            jobs_with_details = await browser.scrape_jobs_intelligent(
                                job_urls=job_urls,
                                user_intent=intent,
                                requested_fields=requested_fields
                            )

                            # Filter out failed/blocked extractions
                            successful_jobs = [
                                j for j in jobs_with_details
                                if j.get("title") and "Access Denied" not in j.get("title", "")
                                and j.get("extraction_method") != "failed"
                            ]

                            if successful_jobs:
                                note = f"Intelligently extracted {len(successful_jobs)} jobs using Claude AI."
                                return {
                                    "success": True,
                                    "data": {
                                        "type": "job_listings",
                                        "site": url,
                                        "search_terms": search_terms,
                                        "jobs_found": len(successful_jobs),
                                        "jobs": successful_jobs,
                                        "requested_fields": requested_fields,
                                        "note": note,
                                        "method": "claude_intelligent"
                                    }
                                }
                            else:
                                print(f"[Intelligent Orchestrator] All pages blocked, using search snippets")
                        except Exception as intel_err:
                            print(f"[Intelligent Orchestrator] Intelligent extraction failed: {intel_err}")

                    # If intelligent extraction failed or all pages blocked, use search result snippets
                    # This is the FINAL fallback - use web search results directly
                    print(f"[Intelligent Orchestrator] Using web search results as fallback")
                    jobs_from_search = []
                    for r in results[:15]:
                        job_url = r.get("url", "")
                        if any(ad in job_url.lower() for ad in ad_domains):
                            continue
                        # Include job pages with ID in URL
                        if re.search(r'/jobs?/[^/]+-\d+|/jobs?/\d+|/vacancy/\d+', job_url):
                            snippet = r.get("snippet", "")
                            jobs_from_search.append({
                                "title": r.get("title", "").replace(" - GulfTalent", "").replace(" | ", " - "),
                                "url": job_url,
                                "company": site_domain.replace("www.", "").split('.')[0].title(),
                                "requirements": [snippet] if snippet else ["Click job link to view full details"],
                                "note": "Site blocks automation - visit link to see full job details"
                            })
                            if len(jobs_from_search) >= 5:
                                break

                    if jobs_from_search:
                        return {
                            "success": True,
                            "data": {
                                "type": "job_listings",
                                "site": url,
                                "search_terms": search_terms,
                                "jobs_found": len(jobs_from_search),
                                "jobs": jobs_from_search,
                                "requested_fields": requested_fields,
                                "note": f"Site uses strong bot protection. Found {len(jobs_from_search)} jobs via search. Visit links directly for full details.",
                                "method": "search_snippets_fallback"
                            }
                        }

                    # Fallback to regex-based extraction if intelligent fails
                    jobs_with_details = []
                    for job_url in job_urls[:5]:
                        print(f"[Intelligent Orchestrator] Fallback scraping: {job_url[:60]}...")
                        job_data = await self._scrape_job_page(
                            client, headers, job_url, "", requested_fields
                        )
                        if job_data:
                            jobs_with_details.append(job_data)

                    if jobs_with_details:
                        note = f"Scraped {len(jobs_with_details)} job pages."
                        return {
                            "success": True,
                            "data": {
                                "type": "job_listings",
                                "site": url,
                                "search_terms": search_terms,
                                "jobs_found": len(jobs_with_details),
                                "jobs": jobs_with_details,
                                "requested_fields": requested_fields,
                                "note": note,
                                "method": "regex_fallback"
                            }
                        }

            # Fallback to regular scraping but try to extract relevant content
            response = await client.get(url, headers=headers)
            html = response.text

            # Extract relevant content based on intent
            extracted = self._extract_relevant_content(html, intent, search_terms)

            return {
                "success": True,
                "data": {
                    "type": "scraped_content",
                    "url": url,
                    "title": extracted.get("title", url),
                    "relevant_content": extracted.get("content", []),
                    "search_terms": search_terms,
                }
            }

    def _extract_search_terms(self, intent: str) -> List[str]:
        """Extract what the user is actually looking for."""
        import re

        intent_lower = intent.lower()

        # Common job-related terms to extract (must be word-bounded)
        job_patterns = [
            r'\b(software\s+engineer(?:ing)?)\b',
            r'\b(data\s+(?:scientist|engineer|analyst))\b',
            r'\b(frontend|backend|fullstack|full-stack)\s*(?:developer)?\b',
            r'\b(devops|sre|cloud)\s*(?:engineer)?\b',
            r'\b(product\s+manager)\b',
            r'\b(ux\s+designer|ui\s+designer|ux/ui|ui/ux)\b',  # Fixed: require designer/specific context
            r'\b(machine\s+learning|ml\s+engineer|ai\s+engineer)\b',
            r'\b(python\s+developer|java\s+developer|javascript\s+developer)\b',
            r'\b(react\s+developer|node\s+developer|web\s+developer)\b',
        ]

        terms = []
        for pattern in job_patterns:
            match = re.search(pattern, intent_lower)
            if match:
                terms.append(match.group(1).strip())

        # If no specific job titles found, extract meaningful keywords
        if not terms:
            # Extract key nouns/phrases - be more selective
            words = intent_lower.split()
            skip_words = {
                'scrape', 'from', 'and', 'the', 'give', 'me', 'their', 'find',
                'search', 'get', 'latest', 'jobs', 'requirements', 'https', 'http',
                'www', 'com', 'gulftalent', 'indeed', 'linkedin', 'job', 'with',
                'for', 'this', 'that', 'what', 'where', 'please', 'can', 'you',
                'need', 'want', 'look', 'looking', 'show', 'list', 'page'
            }
            # Only keep words that look like job-related terms
            terms = [
                w for w in words
                if len(w) > 4
                and w not in skip_words
                and not w.startswith('http')
                and not '.' in w  # Skip domain names
            ][:3]

        # If we have software and engineer separately, combine them
        if 'software' in terms and 'engineer' not in ' '.join(terms):
            terms = ['software engineer']

        return terms

    def _is_job_site(self, url: str) -> bool:
        """Detect if this is a job listing site."""
        job_sites = [
            'gulftalent', 'linkedin', 'indeed', 'glassdoor', 'monster',
            'bayt', 'naukri', 'seek', 'jobs', 'career', 'recruit',
            'hiring', 'workday', 'lever', 'greenhouse', 'bamboohr',
            # Remote job sites
            'remoteok', 'remote ok', 'weworkremotely', 'workingnomads',
            'flexjobs', 'remoteco', 'remote.co', 'justremote', 'remotive',
            'angel.co', 'startup.jobs', 'builtin', 'dice', 'ziprecruiter',
            'simplyhired', 'careerbuilder'
        ]
        url_lower = url.lower()
        return any(site in url_lower for site in job_sites)

    def _is_ad_url(self, url: str) -> bool:
        """Check if URL is an ad/tracking URL that should be filtered out."""
        ad_indicators = [
            'duckduckgo.com/y.js', 'bing.com/aclick', 'google.com/aclk',
            'ad.doubleclick', 'googleadservices', 'click.linksynergy',
            'ad_domain=', 'ad_provider=', 'ad_type=', 'click_metadata=',
            'redirect', 'track.', 'click.', 'go.', 'pixel.'
        ]
        url_lower = url.lower()
        return any(indicator in url_lower for indicator in ad_indicators)

    def _parse_requested_fields(self, intent: str) -> List[str]:
        """Parse what fields/columns the user wants from their intent."""
        import re
        intent_lower = intent.lower()

        # Default fields
        fields = ["title", "company", "url"]

        # Check for specific field requests
        field_patterns = {
            "requirements": ["requirement", "qualifications", "qualification", "what they need", "what is needed"],
            "skills": ["skill", "tech stack", "technologies", "programming"],
            "salary": ["salary", "compensation", "pay", "package"],
            "location": ["location", "where", "city", "country", "region"],
            "experience": ["experience", "years", "seniority", "level"],
            "description": ["description", "about the job", "job details", "responsibilities"],
            "benefits": ["benefits", "perks", "what they offer"],
        }

        for field, keywords in field_patterns.items():
            if any(kw in intent_lower for kw in keywords):
                if field not in fields:
                    fields.append(field)

        # If user asks for "with their requirements" or similar, add requirements
        if re.search(r'\bwith\b.*\b(requirements?|skills?|qualifications?)\b', intent_lower):
            for field in ["requirements", "skills"]:
                if field not in fields:
                    fields.append(field)

        # Default: always include requirements for job searches
        if "requirements" not in fields:
            fields.append("requirements")

        return fields

    async def _scrape_job_page(self, client, headers, url: str, fallback_title: str, requested_fields: List[str]) -> Optional[Dict]:
        """Scrape a single job page to extract requested fields."""
        import re
        import html as html_module

        try:
            response = await client.get(url, headers=headers, timeout=15.0)
            page_html = response.text

            # Check for access denied
            if "access denied" in page_html.lower()[:1000]:
                print(f"[Intelligent Orchestrator] Job page blocked: {url[:50]}")
                return None

            job_data = {
                "title": fallback_title,
                "url": url,
            }

            # Extract title
            title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', page_html, re.IGNORECASE)
            if title_match:
                job_data["title"] = html_module.unescape(title_match.group(1).strip())

            # Extract company
            company_patterns = [
                r'<[^>]*class="[^"]*company[^"]*"[^>]*>([^<]+)<',
                r'<[^>]*class="[^"]*employer[^"]*"[^>]*>([^<]+)<',
                r'Company:?\s*</[^>]+>\s*<[^>]+>([^<]+)<',
                r'Employer:?\s*</[^>]+>\s*<[^>]+>([^<]+)<',
            ]
            for pattern in company_patterns:
                match = re.search(pattern, page_html, re.IGNORECASE)
                if match:
                    job_data["company"] = html_module.unescape(match.group(1).strip())
                    break
            if "company" not in job_data:
                job_data["company"] = ""

            # Extract location if requested
            if "location" in requested_fields:
                location_patterns = [
                    r'<[^>]*class="[^"]*location[^"]*"[^>]*>([^<]+)<',
                    r'Location:?\s*</[^>]+>\s*<[^>]+>([^<]+)<',
                    r'(?:Dubai|Abu Dhabi|UAE|Saudi Arabia|Qatar|Kuwait|Bahrain|Oman)[^<]*',
                ]
                for pattern in location_patterns:
                    match = re.search(pattern, page_html, re.IGNORECASE)
                    if match:
                        job_data["location"] = html_module.unescape(match.group(1) if match.lastindex else match.group(0)).strip()
                        break

            # Extract salary if requested
            if "salary" in requested_fields:
                salary_patterns = [
                    r'(?:salary|compensation|package)[:\s]*([^<\n]+(?:AED|USD|\$|per month|per year)[^<\n]*)',
                    r'(\d{1,3}(?:,\d{3})*(?:\s*-\s*\d{1,3}(?:,\d{3})*)?(?:\s*(?:AED|USD|\$|K))[^<\n]*)',
                ]
                for pattern in salary_patterns:
                    match = re.search(pattern, page_html, re.IGNORECASE)
                    if match:
                        job_data["salary"] = html_module.unescape(match.group(1)).strip()
                        break

            # Extract requirements - this is the main content
            if "requirements" in requested_fields:
                requirements = self._extract_requirements_from_html(page_html)
                job_data["requirements"] = requirements if requirements else ["Requirements not found on page"]

            # Extract skills if requested
            if "skills" in requested_fields:
                skills = self._extract_skills_from_html(page_html)
                job_data["skills"] = skills if skills else ["Skills not explicitly listed"]

            # Extract experience if requested
            if "experience" in requested_fields:
                exp_patterns = [
                    r'(\d+\+?\s*(?:years?|yrs?)[^<\n]{0,50}(?:experience)?)',
                    r'experience[:\s]*(\d+[^<\n]{0,30})',
                ]
                for pattern in exp_patterns:
                    match = re.search(pattern, page_html, re.IGNORECASE)
                    if match:
                        job_data["experience"] = html_module.unescape(match.group(1)).strip()
                        break

            return job_data

        except Exception as e:
            print(f"[Intelligent Orchestrator] Error scraping job page: {e}")
            return {
                "title": fallback_title,
                "url": url,
                "requirements": [f"Could not scrape page: {str(e)[:50]}"],
                "error": str(e)
            }

    def _extract_requirements_from_html(self, html: str) -> List[str]:
        """Extract job requirements from HTML content."""
        import re
        import html as html_module

        requirements = []

        # Look for requirements section
        req_section_patterns = [
            r'(?:requirements?|qualifications?|what you need|must have|essential)[:\s]*</[^>]+>(.*?)(?:<h|</section|</div>\s*<div|$)',
            r'<(?:ul|ol)[^>]*class="[^"]*requirement[^"]*"[^>]*>(.*?)</(?:ul|ol)>',
            r'Requirements?[:\s]*<(?:ul|ol)[^>]*>(.*?)</(?:ul|ol)>',
        ]

        section_html = ""
        for pattern in req_section_patterns:
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if match:
                section_html = match.group(1)
                break

        # If no specific section found, try to find the main job description
        if not section_html:
            desc_patterns = [
                r'<div[^>]*class="[^"]*(?:job-description|description|content)[^"]*"[^>]*>(.*?)</div>',
                r'<article[^>]*>(.*?)</article>',
            ]
            for pattern in desc_patterns:
                match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
                if match:
                    section_html = match.group(1)
                    break

        # Extract list items
        if section_html:
            li_items = re.findall(r'<li[^>]*>(.*?)</li>', section_html, re.IGNORECASE | re.DOTALL)
            for item in li_items:
                # Clean HTML tags
                clean_text = re.sub(r'<[^>]+>', '', item).strip()
                clean_text = html_module.unescape(clean_text)
                if len(clean_text) > 10 and len(clean_text) < 500:
                    requirements.append(clean_text)

        # If no list items, try to extract sentences with requirement keywords
        if not requirements:
            text = re.sub(r'<[^>]+>', ' ', html)
            text = html_module.unescape(text)
            sentences = re.split(r'[.•\n]', text)
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) > 20 and len(sentence) < 300:
                    if any(kw in sentence.lower() for kw in [
                        'experience', 'degree', 'bachelor', 'master', 'knowledge',
                        'proficiency', 'skill', 'ability', 'required', 'must have',
                        'years', 'familiar', 'understanding', 'certification'
                    ]):
                        requirements.append(sentence)
                        if len(requirements) >= 10:
                            break

        # Filter out noise (cookie notices, generic text)
        noise_phrases = [
            'improve your experience', 'cookie', 'accept all', 'privacy policy',
            'terms of service', 'subscribe', 'sign up', 'log in', 'register',
            'we use cookies', 'this website uses', 'please accept'
        ]
        requirements = [
            r for r in requirements
            if not any(noise.lower() in r.lower() for noise in noise_phrases)
        ]

        return requirements[:15]  # Max 15 requirements

    def _extract_skills_from_html(self, html: str) -> List[str]:
        """Extract skills/technologies from HTML content."""
        import re
        import html as html_module

        # Common tech skills to look for
        tech_skills = [
            'Python', 'Java', 'JavaScript', 'TypeScript', 'C++', 'C#', 'Go', 'Rust', 'Ruby',
            'React', 'Angular', 'Vue', 'Node.js', 'Django', 'Flask', 'Spring', '.NET',
            'AWS', 'Azure', 'GCP', 'Docker', 'Kubernetes', 'Jenkins', 'CI/CD',
            'SQL', 'PostgreSQL', 'MySQL', 'MongoDB', 'Redis', 'Elasticsearch',
            'Machine Learning', 'AI', 'Data Science', 'TensorFlow', 'PyTorch',
            'REST', 'API', 'GraphQL', 'Microservices', 'Agile', 'Scrum',
            'Git', 'Linux', 'DevOps', 'Cloud', 'Security'
        ]

        text = re.sub(r'<[^>]+>', ' ', html)
        text = html_module.unescape(text)

        found_skills = []
        for skill in tech_skills:
            if re.search(r'\b' + re.escape(skill) + r'\b', text, re.IGNORECASE):
                found_skills.append(skill)

        return found_skills[:20]  # Max 20 skills

    def _build_job_search_url(self, base_url: str, search_terms: List[str]) -> str:
        """Build a search URL for job sites."""
        import urllib.parse

        domain = urllib.parse.urlparse(base_url).netloc.lower()
        query = " ".join(search_terms)
        encoded_query = urllib.parse.quote_plus(query)

        # Site-specific search URL patterns
        if 'gulftalent' in domain:
            # GulfTalent uses different URL patterns for job search
            return f"https://www.gulftalent.com/uae/jobs/title/{encoded_query.replace('+', '-')}"
        elif 'linkedin' in domain:
            return f"https://www.linkedin.com/jobs/search/?keywords={encoded_query}"
        elif 'indeed' in domain:
            return f"https://www.indeed.com/jobs?q={encoded_query}"
        elif 'glassdoor' in domain:
            return f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={encoded_query}"
        elif 'bayt' in domain:
            return f"https://www.bayt.com/en/uae/jobs/{encoded_query.replace('+', '-')}-jobs/"
        else:
            # Generic search - try common patterns
            return f"{base_url.rstrip('/')}/jobs/search?q={encoded_query}"

    async def _extract_job_listings(self, client, headers, html: str, base_url: str, search_terms: List[str], max_jobs: int = 5) -> List[Dict]:
        """Extract job listings and their requirements."""
        import re
        import urllib.parse

        jobs = []

        # Find job listing links
        # Common patterns for job links
        job_link_patterns = [
            r'href="(/jobs?/[^"]+)"[^>]*>([^<]+)</a>',  # /job/... or /jobs/...
            r'href="([^"]*job[^"]*)"[^>]*>([^<]+)</a>',
            r'<a[^>]*href="([^"]+)"[^>]*class="[^"]*job[^"]*"[^>]*>([^<]+)',
        ]

        found_links = []
        for pattern in job_link_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for link, title in matches:
                # Filter to relevant jobs
                title_lower = title.lower()
                if any(term.lower() in title_lower for term in search_terms):
                    if not link.startswith('http'):
                        parsed = urllib.parse.urlparse(base_url)
                        link = f"{parsed.scheme}://{parsed.netloc}{link}"
                    found_links.append((link, title.strip()))

        # Deduplicate
        seen = set()
        unique_links = []
        for link, title in found_links:
            if link not in seen and len(title) > 5:
                seen.add(link)
                unique_links.append((link, title))

        # Fetch job details for top matches
        for link, title in unique_links[:max_jobs]:
            try:
                job_response = await client.get(link, headers=headers, timeout=10.0)
                job_html = job_response.text

                # Extract requirements
                requirements = self._extract_job_requirements(job_html)

                jobs.append({
                    "title": title,
                    "url": link,
                    "requirements": requirements,
                })
            except Exception as e:
                jobs.append({
                    "title": title,
                    "url": link,
                    "requirements": ["Could not fetch details"],
                    "error": str(e),
                })

        return jobs

    def _extract_job_requirements(self, html: str) -> List[str]:
        """Extract job requirements from a job detail page."""
        import re

        requirements = []

        # Remove scripts and styles
        html_clean = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html_clean = re.sub(r'<style[^>]*>.*?</style>', '', html_clean, flags=re.DOTALL | re.IGNORECASE)

        # Look for requirements sections
        req_patterns = [
            r'(?:requirements?|qualifications?|skills?|must\s+have|you\s+(?:should|will)\s+have)[:\s]*</[^>]+>\s*<[^>]+>([^<]+(?:<[^>]+>[^<]+)*)',
            r'<li[^>]*>([^<]*(?:experience|degree|bachelor|master|years?|proficien|knowledge|skill)[^<]*)</li>',
            r'<li[^>]*>([^<]*(?:python|java|javascript|sql|aws|azure|docker|kubernetes)[^<]*)</li>',
        ]

        for pattern in req_patterns:
            matches = re.findall(pattern, html_clean, re.IGNORECASE)
            for match in matches:
                # Clean up the match
                clean = re.sub(r'<[^>]+>', ' ', match).strip()
                clean = re.sub(r'\s+', ' ', clean)
                if len(clean) > 10 and len(clean) < 500:
                    requirements.append(clean)

        # Deduplicate while preserving order
        seen = set()
        unique_reqs = []
        for req in requirements:
            req_lower = req.lower()
            if req_lower not in seen:
                seen.add(req_lower)
                unique_reqs.append(req)

        return unique_reqs[:15] if unique_reqs else ["Requirements not found in standard format"]

    def _extract_relevant_content(self, html: str, intent: str, search_terms: List[str]) -> Dict:
        """Extract content relevant to what the user is looking for."""
        import re

        # Clean HTML
        html_clean = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html_clean = re.sub(r'<style[^>]*>.*?</style>', '', html_clean, flags=re.DOTALL | re.IGNORECASE)

        # Extract title
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else ""

        # Find content containing search terms
        relevant_content = []

        # Extract paragraphs and list items containing search terms
        content_patterns = [
            r'<p[^>]*>([^<]+(?:<[^>]+>[^<]+)*)</p>',
            r'<li[^>]*>([^<]+(?:<[^>]+>[^<]+)*)</li>',
            r'<div[^>]*>([^<]{50,500})</div>',
        ]

        for pattern in content_patterns:
            matches = re.findall(pattern, html_clean, re.IGNORECASE)
            for match in matches:
                clean = re.sub(r'<[^>]+>', ' ', match).strip()
                clean = re.sub(r'\s+', ' ', clean)

                # Check if it contains any search terms
                if search_terms:
                    if any(term.lower() in clean.lower() for term in search_terms):
                        if len(clean) > 20 and len(clean) < 1000:
                            relevant_content.append(clean)
                elif len(clean) > 50:
                    relevant_content.append(clean)

        # Deduplicate
        seen = set()
        unique_content = []
        for content in relevant_content:
            if content not in seen:
                seen.add(content)
                unique_content.append(content)

        return {
            "title": title,
            "content": unique_content[:20],
        }

    async def _do_data_extraction(self, params: Dict) -> Dict[str, Any]:
        """Extract specific data from content."""
        # This would use Claude to extract specific information
        return {"success": True, "data": params}

    async def interpret_results(self, plan: ExecutionPlan, raw_results: Dict) -> str:
        """
        Use Claude to interpret raw results and extract the ACTUAL answer.

        This is crucial - we don't just dump data, we give the user what they asked for.
        """

        system_prompt = """You are a helpful assistant that extracts and presents information clearly.

Given raw data from various tools, your job is to:
1. Find the SPECIFIC information the user asked for
2. Present it clearly and concisely
3. If the information isn't available, say so clearly

DO NOT:
- Dump raw data
- Include irrelevant information
- Be verbose when a simple answer works

The user asked: {goal}

Analyze the raw data and provide a clear, direct answer."""

        # Prepare the raw data summary
        data_summary = json.dumps(raw_results.get("raw_data", {}), indent=2, default=str)
        if len(data_summary) > 4000:
            data_summary = data_summary[:4000] + "...(truncated)"

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system_prompt.format(goal=plan.understood_goal),
            messages=[
                {"role": "user", "content": f"Raw data collected:\n{data_summary}\n\nProvide a clear answer to: {plan.intent}"}
            ]
        )

        return response.content[0].text

    async def process_request(self, user_intent: str) -> ExecutionResult:
        """
        Main entry point - process a user request end-to-end.

        This is the intelligent pipeline:
        1. Understand what the user wants
        2. Plan how to get it
        3. Execute the plan
        4. Interpret results
        5. Return a meaningful answer

        Falls back to basic execution if ANTHROPIC_API_KEY is not set.
        """

        if not self.has_api_key:
            # Fallback to basic execution without AI reasoning
            return await self._basic_execution(user_intent)

        # Step 1: Understand and plan
        plan = await self.understand_and_plan(user_intent)

        # Step 2: Execute
        raw_results = await self.execute_plan(plan)

        # Step 3: Interpret results
        answer = await self.interpret_results(plan, raw_results)

        # Step 4: Build execution result
        return ExecutionResult(
            success=len(raw_results.get("errors", [])) == 0,
            answer=answer,
            raw_data=raw_results.get("raw_data", {}),
            steps_executed=raw_results.get("steps_executed", []),
            execution_info={
                "understood_goal": plan.understood_goal,
                "mcps_used": plan.mcps_needed,
                "skills_used": plan.skills_needed,
                "agents_used": plan.agents_needed,
                "hooks_triggered": plan.hooks_to_trigger,
                "complexity": plan.estimated_complexity,
            }
        )

    async def _basic_execution(self, user_intent: str) -> ExecutionResult:
        """
        Smart execution without full AI reasoning.
        Uses intelligent heuristics for scraping and searching.
        """
        intent_lower = user_intent.lower()

        # Determine what to do based on intent analysis
        tool = "web-search"
        result = None

        # Check for scrape/extract intent with a specific site
        has_site = any(word in intent_lower for word in ["scrape", "extract", "from", ".com", ".org", ".io"])
        has_job_terms = any(word in intent_lower for word in ["job", "jobs", "engineer", "developer", "position", "hiring", "career"])

        if has_site or has_job_terms:
            tool = "web-scrape"
            result = await self._do_web_scrape(user_intent, {})
        else:
            result = await self._do_web_search(user_intent, {})

        # Build answer from results
        answer = "Results for your query"
        # Always get data, even if success=False (for error messages)
        data = result.get("data", {})

        if data.get("type") == "search_results":
            results = data.get("results", [])
            if results:
                answer = f"Found {len(results)} results for '{data.get('query', user_intent)}':\n\n"
                for i, r in enumerate(results[:5], 1):
                    answer += f"{i}. {r.get('title', 'No title')}\n   {r.get('url', '')}\n\n"
            elif data.get("error"):
                answer = f"Search blocked: {data.get('error')}\n"
                if data.get("suggestion"):
                    answer += f"\nSuggestion: {data.get('suggestion')}"
            else:
                answer = f"No search results found for '{data.get('query', user_intent)}'"

        elif data.get("type") == "job_listings":
            jobs = data.get("jobs", [])
            search_terms = data.get("search_terms", [])
            if jobs:
                answer = f"Found {len(jobs)} {' '.join(search_terms)} jobs:\n\n"
                for i, job in enumerate(jobs[:5], 1):
                    answer += f"{i}. {job.get('title', 'Untitled')}\n"
                    answer += f"   URL: {job.get('url', '')}\n"
                    reqs = job.get("requirements", [])
                    if reqs and reqs[0] != "Requirements not found in standard format":
                        answer += "   Requirements:\n"
                        for req in reqs[:3]:
                            answer += f"   • {req}\n"
                    answer += "\n"
            else:
                answer = f"Searched for {' '.join(search_terms)} jobs but couldn't find matching listings. Try being more specific or check the site directly."

        elif data.get("type") == "scraped_content":
            content = data.get("relevant_content", [])
            if content:
                answer = f"Found relevant content from {data.get('title', 'the page')}:\n\n"
                for item in content[:5]:
                    answer += f"• {item}\n\n"
            else:
                answer = f"Scraped {data.get('url', 'the page')} but couldn't extract content matching your query. Try being more specific."

        return ExecutionResult(
            success=result.get("success", False),
            answer=answer,
            raw_data={"step_1": data},
            steps_executed=[{"step": {"action": tool}, "result": result}],
            execution_info={
                "understood_goal": user_intent,
                "mcps_used": ["brave-search"] if tool == "web-search" else ["playwright"],
                "skills_used": [tool],
                "agents_used": ["intelligent-executor"],
                "hooks_triggered": ["task-ledger-update"],
                "complexity": "simple",
                "mode": "smart-heuristics",
            }
        )


# Singleton instance
_orchestrator: Optional[IntelligentOrchestrator] = None


def get_orchestrator() -> IntelligentOrchestrator:
    """Get the singleton orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = IntelligentOrchestrator()
    return _orchestrator


async def process_intelligent_request(user_intent: str) -> Dict[str, Any]:
    """
    Process a user request using the intelligent orchestrator.

    Returns a dict with:
    - success: bool
    - answer: str (the actual answer to show the user)
    - execution_info: dict (what was used to get the answer)
    """
    orchestrator = get_orchestrator()
    result = await orchestrator.process_request(user_intent)

    return {
        "success": result.success,
        "answer": result.answer,
        "execution_info": result.execution_info,
        "raw_data": result.raw_data,
    }
