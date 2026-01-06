"""
Browser Automation Skill

Uses Playwright to browse websites like a real user:
- Navigates pages
- Clicks buttons
- Fills forms
- Waits for content to load
- Extracts data intelligently

This skill is triggered when direct HTTP scraping fails
or when the user explicitly requests browser automation.
"""

import asyncio
import json
import re
from urllib.parse import urlencode, quote_plus
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


# Job site URL builders - how to construct search URLs for each site
JOB_SITE_PATTERNS = {
    "gulftalent.com": {
        "search_url": "https://www.gulftalent.com/jobs?keywords={query}",
        "job_selectors": [
            "a[href*='/job/']",  # Direct job links
            ".job-listing", ".job-card", ".vacancy",
            "[class*='job-item']", "[class*='job-result']",
            ".search-result", "article", ".listing-item",
            "tr[onclick]", "div[data-job]", "li.result"
        ],
        "title_selector": "h2, h3, .title, a, span.job-title",
        "company_selector": ".company, .employer, span[class*='company']",
        "requirements_selector": ".description, .snippet, p",
    },
    "indeed.com": {
        "search_url": "https://www.indeed.com/jobs?q={query}",
        "job_selectors": [".job_seen_beacon", ".result", ".jobsearch-ResultsList > li"],
        "title_selector": ".jobTitle a, h2.jobTitle",
        "company_selector": ".companyName, [data-testid='company-name']",
        "requirements_selector": ".job-snippet, .jobCardShelfContainer",
    },
    "linkedin.com": {
        "search_url": "https://www.linkedin.com/jobs/search/?keywords={query}",
        "job_selectors": [".jobs-search-results__list-item", ".job-card-container"],
        "title_selector": ".job-card-list__title, .base-search-card__title",
        "company_selector": ".job-card-container__company-name, .base-search-card__subtitle",
        "requirements_selector": ".job-card-list__insight, .base-search-card__metadata",
    },
    "glassdoor.com": {
        "search_url": "https://www.glassdoor.com/Job/jobs.htm?sc.keyword={query}",
        "job_selectors": [".react-job-listing", ".jobCard"],
        "title_selector": ".job-title, [data-test='jobTitle']",
        "company_selector": ".job-company, [data-test='employer-name']",
        "requirements_selector": ".job-snippet",
    },
    "bayt.com": {
        "search_url": "https://www.bayt.com/en/jobs/?search={query}",
        "job_selectors": [".list-results__item", ".job-card"],
        "title_selector": ".title a, .job-title",
        "company_selector": ".company, .employer-name",
        "requirements_selector": ".description, .requirements",
    },
    "naukrigulf.com": {
        "search_url": "https://www.naukrigulf.com/{query}-jobs",
        "job_selectors": [".srp-result-card", ".job-tuple"],
        "title_selector": ".job-title a, .desig",
        "company_selector": ".company-name, .org-name",
        "requirements_selector": ".description, .more-info",
    },
}

# Generic fallback for unknown sites
DEFAULT_JOB_PATTERNS = {
    "job_selectors": [
        "article[class*='job']", "div[class*='job-card']", "div[class*='job-listing']",
        "li[class*='job']", ".vacancy", ".search-result", "[data-job-id]",
        "div[class*='vacancy']", ".listing", ".result-card"
    ],
    "title_selector": "h2, h3, h4, .title, .job-title, a[class*='title']",
    "company_selector": ".company, .employer, [class*='company']",
    "requirements_selector": ".description, .requirements, .skills, .snippet, p",
}

# Job detail page selectors - for extracting from individual job pages
JOB_DETAIL_SELECTORS = {
    "gulftalent.com": {
        "title": "h1, .job-title, .vacancy-title",
        "company": ".company-name, .employer-name, [class*='company']",
        "location": ".location, .job-location, [class*='location']",
        "requirements": [
            ".job-description", ".requirements", ".qualifications",
            "#job-description", "[class*='description']", "[class*='requirement']",
            "section:has-text('Requirements')", "section:has-text('Qualifications')",
            ".skills", "[class*='skill']"
        ],
        "salary": ".salary, .compensation, [class*='salary']",
        "experience": ".experience, [class*='experience']",
    },
    "default": {
        "title": "h1, .job-title, [class*='title']",
        "company": ".company, .employer, [class*='company'], [class*='employer']",
        "location": ".location, [class*='location']",
        "requirements": [
            ".job-description", ".description", ".requirements", ".qualifications",
            "#description", "#requirements", "[class*='description']",
            "[class*='requirement']", "[class*='qualification']",
            "section", "article", ".content", "main"
        ],
        "salary": ".salary, [class*='salary'], [class*='compensation']",
        "experience": ".experience, [class*='experience']",
    }
}


@dataclass
class BrowsingAction:
    """A single browsing action."""
    action: str  # navigate, click, fill, scroll, wait, extract
    selector: Optional[str] = None
    value: Optional[str] = None
    wait_for: Optional[str] = None


class BrowserAutomationSkill:
    """
    Intelligent browser automation using Playwright.

    This skill can:
    - Navigate to URLs
    - Click elements (buttons, links)
    - Fill forms
    - Wait for dynamic content
    - Extract structured data
    - Take screenshots
    - Handle popups and modals
    """

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize Playwright browser with stealth mode to avoid detection."""
        try:
            from playwright.async_api import async_playwright
            self.playwright = await async_playwright().start()

            # Launch with stealth settings
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-infobars',
                    '--window-position=0,0',
                    '--ignore-certificate-errors',
                    '--ignore-certificate-errors-spki-list',
                ]
            )

            # Create context with realistic settings to avoid bot detection
            self.context = await self.browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                locale='en-US',
                timezone_id='America/New_York',
                permissions=['geolocation'],
                geolocation={'latitude': 40.7128, 'longitude': -74.0060},
                color_scheme='light',
            )

            # Add stealth scripts to avoid detection
            await self.context.add_init_script("""
                // Overwrite navigator.webdriver
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });

                // Overwrite chrome.runtime for headless detection
                window.chrome = {
                    runtime: {}
                };

                // Mock plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });

                // Mock languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });

                // Mock hardware concurrency
                Object.defineProperty(navigator, 'hardwareConcurrency', {
                    get: () => 8
                });

                // Mock platform
                Object.defineProperty(navigator, 'platform', {
                    get: () => 'Win32'
                });
            """)

            self.page = await self.context.new_page()
            self._initialized = True
            return True
        except ImportError:
            print("Playwright not installed. Run: pip install playwright && playwright install")
            return False
        except Exception as e:
            print(f"Failed to initialize Playwright: {e}")
            return False

    async def close(self):
        """Close the browser."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self._initialized = False

    async def browse_and_extract(
        self,
        url: str,
        intent: str,
        search_terms: List[str] = None,
        max_pages: int = 5
    ) -> Dict[str, Any]:
        """
        Intelligently browse a website and extract requested data.

        This is the main entry point for smart browsing.
        """
        if not self._initialized:
            if not await self.initialize():
                return {
                    "success": False,
                    "error": "Playwright not available. Install with: pip install playwright && playwright install chromium"
                }

        try:
            # Check if this is a job site and we have search terms - build proper URL
            is_job_intent = "job" in intent.lower()
            site_pattern = self._get_site_pattern(url)

            if is_job_intent and search_terms and site_pattern:
                # Build the proper search URL for this job site
                search_query = "+".join(search_terms)
                search_url = site_pattern["search_url"].format(query=quote_plus(" ".join(search_terms)))
                print(f"Built job search URL: {search_url}")
                url = search_url

            # Navigate to the URL
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)  # Wait for dynamic content

            # Analyze what type of page this is
            page_type = await self._detect_page_type()

            # Handle based on page type and intent
            if is_job_intent or page_type == "job_site":
                return await self._handle_job_site(intent, search_terms, site_pattern)
            elif "search" in page_type:
                return await self._handle_search_page(intent, search_terms)
            else:
                return await self._handle_generic_page(intent, search_terms)

        except Exception as e:
            # If browsing failed, return helpful info with search URL fallback
            return {
                "success": False,
                "error": str(e),
                "url": url,
                "search_url": self._build_google_search_url(intent, search_terms),
                "note": "Browser automation failed. Try the search URL instead.",
            }

    def _get_site_pattern(self, url: str) -> Optional[Dict]:
        """Get the site-specific pattern for a URL."""
        url_lower = url.lower()
        for site, pattern in JOB_SITE_PATTERNS.items():
            if site in url_lower:
                return pattern
        return None

    def _build_google_search_url(self, intent: str, search_terms: List[str] = None) -> str:
        """Build a Google search URL as fallback."""
        query = intent
        if search_terms:
            query = f"{' '.join(search_terms)} jobs"
        return f"https://www.google.com/search?q={quote_plus(query)}"

    async def _detect_page_type(self) -> str:
        """Detect what type of page we're on."""
        # Check for common indicators
        url = self.page.url.lower()
        title = await self.page.title()
        title_lower = title.lower() if title else ""

        if any(x in url for x in ['job', 'career', 'hiring', 'recruit']):
            return "job_site"
        if any(x in url for x in ['search', 'query', 'q=']):
            return "search"
        if any(x in title_lower for x in ['job', 'career', 'hiring']):
            return "job_site"

        return "generic"

    async def _handle_job_site(
        self,
        intent: str,
        search_terms: List[str] = None,
        site_pattern: Dict = None
    ) -> Dict[str, Any]:
        """Handle job site browsing - search and extract job listings."""

        # If we haven't already navigated to search results, try using search input
        current_url = self.page.url.lower()
        has_search_results = any(x in current_url for x in ['search', 'jobs?', 'keyword', 'q='])

        if not has_search_results:
            search_input = await self._find_search_input()
            if search_input and search_terms:
                search_query = " ".join(search_terms)
                await search_input.fill(search_query)
                await search_input.press("Enter")
                await asyncio.sleep(3)

        # Use site-specific patterns if available
        patterns = site_pattern or DEFAULT_JOB_PATTERNS

        # Extract job listings with intelligent patterns
        jobs = await self._extract_job_listings_smart(patterns)

        # If we got no results, try scrolling to load more
        if len(jobs) == 0:
            await self._scroll_page()
            await asyncio.sleep(2)
            jobs = await self._extract_job_listings_smart(patterns)

        # If still no results, provide helpful fallback
        if len(jobs) == 0:
            return {
                "success": True,
                "type": "job_listings",
                "url": self.page.url,
                "title": await self.page.title(),
                "search_terms": search_terms,
                "jobs_found": 0,
                "jobs": [],
                "search_url": self._build_google_search_url(intent, search_terms),
                "note": "No jobs found on this page. The site may use heavy JavaScript or require login. Try the Google search link.",
            }

        return {
            "success": True,
            "type": "job_listings",
            "url": self.page.url,
            "title": await self.page.title(),
            "search_terms": search_terms,
            "jobs_found": len(jobs),
            "jobs": jobs,
        }

    async def _scroll_page(self):
        """Scroll the page to load dynamic content."""
        try:
            await self.page.evaluate('window.scrollTo(0, document.body.scrollHeight / 2)')
            await asyncio.sleep(1)
            await self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        except:
            pass

    async def _extract_job_listings_smart(self, patterns: Dict) -> List[Dict]:
        """Extract job listings using smart patterns."""
        jobs = []

        # Try each job selector in order
        for selector in patterns.get("job_selectors", DEFAULT_JOB_PATTERNS["job_selectors"]):
            try:
                elements = await self.page.query_selector_all(selector)
                if elements and len(elements) > 0:
                    print(f"Found {len(elements)} job elements with selector: {selector}")

                    for element in elements[:15]:  # Max 15 jobs
                        job = await self._extract_job_from_element_smart(element, patterns)
                        if job and job.get("title"):
                            jobs.append(job)

                    if jobs:
                        break
            except Exception as e:
                print(f"Selector {selector} failed: {e}")
                continue

        # Deduplicate jobs by title
        seen_titles = set()
        unique_jobs = []
        for job in jobs:
            title_key = job.get("title", "").lower().strip()
            if title_key and title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_jobs.append(job)

        return unique_jobs

    async def _extract_job_from_element_smart(self, element, patterns: Dict) -> Optional[Dict]:
        """Extract job details from a single element using patterns."""
        try:
            # Get title
            title = ""
            title_selector = patterns.get("title_selector", DEFAULT_JOB_PATTERNS["title_selector"])
            for sel in title_selector.split(", "):
                try:
                    title_el = await element.query_selector(sel)
                    if title_el:
                        title = await title_el.inner_text()
                        if title and len(title.strip()) > 3:
                            break
                except:
                    continue

            if not title or len(title.strip()) < 3:
                # Try getting text directly from element
                title = await element.inner_text()
                if title:
                    # Take first line as title
                    title = title.strip().split("\n")[0]

            if not title or len(title.strip()) < 3:
                return None

            # Get link
            href = ""
            try:
                link_el = await element.query_selector("a[href]")
                if link_el:
                    href = await link_el.get_attribute("href")
            except:
                pass

            # Get company
            company = ""
            company_selector = patterns.get("company_selector", DEFAULT_JOB_PATTERNS["company_selector"])
            for sel in company_selector.split(", "):
                try:
                    company_el = await element.query_selector(sel)
                    if company_el:
                        company = await company_el.inner_text()
                        if company:
                            break
                except:
                    continue

            # Get requirements/description
            requirements = []
            req_selector = patterns.get("requirements_selector", DEFAULT_JOB_PATTERNS["requirements_selector"])
            for sel in req_selector.split(", "):
                try:
                    req_el = await element.query_selector(sel)
                    if req_el:
                        req_text = await req_el.inner_text()
                        if req_text and len(req_text.strip()) > 10:
                            # Split by common separators and clean up
                            parts = re.split(r'[•\n\r,;]', req_text)
                            for part in parts:
                                cleaned = part.strip()
                                if len(cleaned) > 5 and len(cleaned) < 200:
                                    requirements.append(cleaned)
                            break
                except:
                    continue

            # If no requirements found, add a placeholder
            if not requirements:
                requirements = ["Click to view full job details and requirements"]

            return {
                "title": title.strip()[:150],
                "url": href if href and href.startswith("http") else self._make_absolute_url(href) if href else "",
                "company": company.strip()[:100] if company else "",
                "requirements": requirements[:10],  # Max 10 requirements
            }

        except Exception as e:
            print(f"Error extracting job: {e}")
            return None

    async def _find_search_input(self):
        """Find the search input on the page."""
        selectors = [
            'input[type="search"]',
            'input[name*="search"]',
            'input[name*="keyword"]',
            'input[name*="query"]',
            'input[placeholder*="search" i]',
            'input[placeholder*="job" i]',
            '#search',
            '.search-input',
        ]

        for selector in selectors:
            try:
                element = await self.page.query_selector(selector)
                if element:
                    return element
            except:
                continue

        return None

    def _make_absolute_url(self, relative_url: str) -> str:
        """Convert relative URL to absolute."""
        from urllib.parse import urljoin
        return urljoin(self.page.url, relative_url)

    async def _handle_search_page(
        self,
        intent: str,
        search_terms: List[str] = None
    ) -> Dict[str, Any]:
        """Handle search result pages."""
        results = []

        # Extract search results
        result_selectors = [
            '.search-result',
            '.result',
            'article',
            '.listing',
        ]

        for selector in result_selectors:
            elements = await self.page.query_selector_all(selector)
            if elements:
                for el in elements[:10]:
                    try:
                        title_el = await el.query_selector('h2, h3, a')
                        link_el = await el.query_selector('a')
                        desc_el = await el.query_selector('p, .description')

                        title = await title_el.inner_text() if title_el else ""
                        href = await link_el.get_attribute("href") if link_el else ""
                        desc = await desc_el.inner_text() if desc_el else ""

                        if title:
                            results.append({
                                "title": title.strip()[:100],
                                "url": self._make_absolute_url(href) if href else "",
                                "snippet": desc.strip()[:200] if desc else "",
                            })
                    except:
                        continue

                if results:
                    break

        return {
            "success": True,
            "type": "search_results",
            "url": self.page.url,
            "results": results,
        }

    async def _handle_generic_page(
        self,
        intent: str,
        search_terms: List[str] = None
    ) -> Dict[str, Any]:
        """Handle generic pages - extract relevant content."""

        # Get page content
        title = await self.page.title()
        content = await self.page.content()

        # Extract text content
        text_content = await self.page.evaluate('''() => {
            const body = document.body;
            const walker = document.createTreeWalker(
                body,
                NodeFilter.SHOW_TEXT,
                null,
                false
            );
            let text = [];
            while (walker.nextNode()) {
                const t = walker.currentNode.textContent.trim();
                if (t.length > 20) {
                    text.push(t);
                }
            }
            return text.slice(0, 50);
        }''')

        # Filter for relevant content
        relevant = []
        if search_terms:
            for text in text_content:
                if any(term.lower() in text.lower() for term in search_terms):
                    relevant.append(text)
        else:
            relevant = text_content[:20]

        return {
            "success": True,
            "type": "scraped_content",
            "url": self.page.url,
            "title": title,
            "relevant_content": relevant[:20],
        }

    async def click_and_extract(self, selector: str) -> Dict[str, Any]:
        """Click an element and extract resulting content."""
        try:
            await self.page.click(selector, timeout=5000)
            await asyncio.sleep(2)

            title = await self.page.title()
            url = self.page.url

            return {
                "success": True,
                "new_url": url,
                "new_title": title,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def take_screenshot(self, path: str = None) -> Dict[str, Any]:
        """Take a screenshot of the current page."""
        try:
            if not path:
                path = f"screenshot_{asyncio.get_event_loop().time()}.png"

            await self.page.screenshot(path=path, full_page=True)

            return {
                "success": True,
                "path": path,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def intelligent_extract(
        self,
        url: str,
        user_intent: str,
        requested_fields: List[str] = None
    ) -> Dict[str, Any]:
        """
        TRULY INTELLIGENT extraction using Claude's vision capabilities.

        This method:
        1. Navigates to the URL like a real user
        2. Takes a screenshot of the page
        3. Uses Claude Code CLI to analyze the screenshot
        4. Extracts EXACTLY what the user asked for - no patterns, pure AI understanding

        Works on ANY website - no hardcoded patterns needed!
        """
        import shutil
        import subprocess
        import base64
        import tempfile
        import os

        # Reinitialize browser for fresh state (stealth mode)
        if self._initialized:
            await self.close()
        if not await self.initialize():
            return {"success": False, "error": "Failed to initialize browser"}

        try:
            # Step 1: Navigate to the page with random delay (more human-like)
            print(f"[Intelligent Extract] Navigating to: {url}")
            import random
            await asyncio.sleep(random.uniform(1, 3))  # Random delay

            await self.page.goto(url, wait_until="networkidle", timeout=45000)
            await asyncio.sleep(random.uniform(2, 4))  # Random delay

            # Check for access denied early
            page_title = await self.page.title()
            if "access denied" in page_title.lower() or "blocked" in page_title.lower():
                print(f"[Intelligent Extract] Page blocked: {page_title}")
                return {
                    "success": False,
                    "error": "Access denied by website",
                    "data": {"url": url, "title": "Access Denied - Site blocks automation"}
                }

            # Handle cookie popups, etc.
            await self._dismiss_popups()

            # Scroll to load content (more human-like)
            await self.page.evaluate("window.scrollTo(0, 300)")
            await asyncio.sleep(0.5)
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3)")
            await asyncio.sleep(1)

            # Step 2: Take a screenshot
            screenshot_path = tempfile.mktemp(suffix=".png")
            await self.page.screenshot(path=screenshot_path, full_page=False)  # Viewport only for speed
            print(f"[Intelligent Extract] Screenshot saved: {screenshot_path}")

            # Step 3: Get page HTML for context (first 50KB)
            page_html = await self.page.content()
            page_text = await self.page.evaluate("document.body.innerText")
            page_text = page_text[:30000] if page_text else ""  # Limit text size

            # Step 4: Use Claude Code CLI to analyze
            claude_path = shutil.which("claude")
            if not claude_path:
                print("[Intelligent Extract] Claude CLI not found, falling back to regex extraction")
                return await self._fallback_extract(url, user_intent, requested_fields)

            # Build the prompt for Claude
            fields_str = ", ".join(requested_fields) if requested_fields else "all relevant information"
            prompt = f"""You are analyzing a job posting page. The user wants to find: {user_intent}

Please extract the following fields: {fields_str}

Here is the text content of the page:
---
{page_text[:20000]}
---

IMPORTANT RULES:
1. Only extract information that is ACTUALLY on this specific job page
2. For "requirements" - extract the actual job requirements/qualifications listed, NOT generic website text
3. For "skills" - extract skills that are REQUIRED for this job, not just mentioned anywhere
4. For "company" - extract the actual hiring company name
5. For "salary" - extract salary info if mentioned
6. For "location" - extract the job location
7. For "date" or "posted" - extract when the job was posted
8. Ignore cookie notices, navigation menus, footer text, etc.
9. If a field is not found on this page, say "Not found on page"

Return the data as a JSON object with the requested fields.
Example format:
{{
  "title": "Software Engineer",
  "company": "Acme Corp",
  "location": "Dubai, UAE",
  "requirements": ["5+ years experience", "Bachelor's in CS", "Python proficiency"],
  "skills": ["Python", "AWS", "Docker"],
  "salary": "AED 15,000 - 25,000/month",
  "date_posted": "January 3, 2026"
}}

Return ONLY the JSON, no other text."""

            # Call Claude CLI
            try:
                result = subprocess.run(
                    [claude_path, "-p", prompt, "--output-format", "text"],
                    capture_output=True,
                    text=True,
                    timeout=90,
                    env={**os.environ, "TERM": "dumb"}  # Prevent ANSI codes
                )
                claude_response = result.stdout.strip()
                print(f"[Intelligent Extract] Claude response length: {len(claude_response)}")

                # Debug: print first 200 chars of response
                if claude_response:
                    print(f"[Intelligent Extract] Response preview: {claude_response[:300]}...")

                # Parse JSON from response - try multiple strategies
                extracted_data = None

                # Strategy 1: Find JSON block with curly braces
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', claude_response, re.DOTALL)
                if json_match:
                    try:
                        extracted_data = json.loads(json_match.group())
                    except json.JSONDecodeError:
                        pass

                # Strategy 2: Try to find JSON after "```json" or similar
                if not extracted_data:
                    code_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', claude_response)
                    if code_match:
                        try:
                            extracted_data = json.loads(code_match.group(1))
                        except json.JSONDecodeError:
                            pass

                # Strategy 3: Try the whole response as JSON
                if not extracted_data:
                    try:
                        extracted_data = json.loads(claude_response)
                    except json.JSONDecodeError:
                        pass

                if extracted_data:
                    extracted_data["url"] = url
                    extracted_data["extraction_method"] = "claude_intelligent"
                    return {
                        "success": True,
                        "data": extracted_data
                    }
                else:
                    print(f"[Intelligent Extract] Could not parse JSON, using text extraction")
                    # Try to extract key info from text response
                    return await self._extract_from_text_response(url, claude_response, requested_fields)

            except subprocess.TimeoutExpired:
                print("[Intelligent Extract] Claude CLI timed out")
                return await self._fallback_extract(url, user_intent, requested_fields)
            except Exception as e:
                print(f"[Intelligent Extract] Error: {e}")
                return await self._fallback_extract(url, user_intent, requested_fields)

        except Exception as e:
            print(f"[Intelligent Extract] Error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            # Clean up screenshot
            if 'screenshot_path' in locals() and os.path.exists(screenshot_path):
                os.remove(screenshot_path)

    async def _dismiss_popups(self):
        """Try to dismiss common popups (cookie notices, etc.)"""
        popup_selectors = [
            "button:has-text('Accept')",
            "button:has-text('Accept All')",
            "button:has-text('I Accept')",
            "button:has-text('OK')",
            "button:has-text('Got it')",
            "[class*='cookie'] button",
            "[class*='consent'] button",
            "[id*='cookie'] button",
        ]
        for selector in popup_selectors:
            try:
                element = await self.page.query_selector(selector)
                if element:
                    await element.click()
                    await asyncio.sleep(0.5)
                    break
            except:
                continue

    async def _extract_from_text_response(self, url: str, text_response: str, requested_fields: List[str]) -> Dict[str, Any]:
        """Extract structured data from Claude's text response when JSON parsing fails."""
        data = {"url": url, "extraction_method": "claude_text_parsed"}

        # Try to extract title from page
        try:
            data["title"] = await self.page.title()
            # Clean up title
            if " - " in data["title"]:
                data["title"] = data["title"].split(" - ")[0].strip()
        except:
            data["title"] = "Unknown"

        # Look for patterns in the text response
        lines = text_response.split('\n')
        requirements = []
        skills = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Look for company
            if 'company' in line.lower() and ':' in line:
                data["company"] = line.split(':', 1)[1].strip().strip('"')

            # Look for location
            if 'location' in line.lower() and ':' in line:
                data["location"] = line.split(':', 1)[1].strip().strip('"')

            # Look for requirements (lines starting with - or *)
            if line.startswith('-') or line.startswith('*') or line.startswith('•'):
                clean_line = line.lstrip('-*• ').strip()
                if len(clean_line) > 10:
                    requirements.append(clean_line)

            # Look for skills mentioned
            skill_keywords = ['python', 'java', 'javascript', 'react', 'angular', 'aws', 'azure', 'docker', 'kubernetes', 'sql', 'node']
            for skill in skill_keywords:
                if skill.lower() in line.lower() and skill.title() not in skills:
                    skills.append(skill.title())

        if requirements:
            data["requirements"] = requirements[:10]
        if skills:
            data["skills"] = skills[:15]

        return {"success": True, "data": data}

    async def _fallback_extract(self, url: str, user_intent: str, requested_fields: List[str]) -> Dict[str, Any]:
        """Fallback extraction when Claude CLI is not available."""
        # Use the existing regex-based extraction
        page_text = await self.page.evaluate("document.body.innerText")
        return {
            "success": True,
            "data": {
                "url": url,
                "title": await self.page.title(),
                "raw_text": page_text[:5000] if page_text else "",
                "extraction_method": "fallback_text"
            }
        }

    async def scrape_jobs_intelligent(
        self,
        job_urls: List[str],
        user_intent: str,
        requested_fields: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Intelligently scrape multiple job pages using Claude vision.

        This is the MAIN method for intelligent job extraction.
        """
        if not await self.initialize():
            return []

        jobs = []
        if not requested_fields:
            # Parse what user wants from their intent
            requested_fields = self._parse_fields_from_intent(user_intent)

        print(f"[Intelligent Scrape] Will extract: {requested_fields}")
        print(f"[Intelligent Scrape] Processing {len(job_urls)} job URLs")

        for i, url in enumerate(job_urls[:5]):  # Max 5 jobs
            print(f"[Intelligent Scrape] Processing job {i+1}/{min(len(job_urls), 5)}: {url[:60]}...")
            result = await self.intelligent_extract(url, user_intent, requested_fields)

            if result.get("success") and result.get("data"):
                jobs.append(result["data"])
            else:
                # Still add with URL so user can visit manually
                jobs.append({
                    "url": url,
                    "title": "Could not extract - visit page directly",
                    "extraction_method": "failed"
                })

            # Small delay between pages
            await asyncio.sleep(1)

        return jobs

    def _parse_fields_from_intent(self, intent: str) -> List[str]:
        """Parse what fields user wants from their intent."""
        intent_lower = intent.lower()
        fields = ["title", "company", "url"]  # Always include these

        field_keywords = {
            "requirements": ["requirement", "qualification", "need", "must have"],
            "skills": ["skill", "technology", "tech stack", "programming"],
            "salary": ["salary", "pay", "compensation", "package"],
            "location": ["location", "where", "city", "country"],
            "experience": ["experience", "years", "senior", "junior"],
            "date_posted": ["date", "posted", "when", "ago"],
            "description": ["description", "about", "overview", "summary"],
            "benefits": ["benefit", "perk", "offer"],
        }

        for field, keywords in field_keywords.items():
            if any(kw in intent_lower for kw in keywords):
                if field not in fields:
                    fields.append(field)

        # Default: always include requirements for job searches
        if "job" in intent_lower and "requirements" not in fields:
            fields.append("requirements")

        return fields

    async def scrape_jobs_deep(
        self,
        site_url: str,
        search_query: str,
        max_jobs: int = 5
    ) -> Dict[str, Any]:
        """
        Deep scrape job listings - visits each job page to extract full details.

        This method:
        1. Navigates to the job search page
        2. Extracts job listing URLs
        3. Visits EACH job page individually
        4. Extracts detailed requirements, skills, salary, etc.
        5. Returns comprehensive job data
        """
        if not await self.initialize():
            return {"success": False, "error": "Failed to initialize browser"}

        jobs = []
        base_url = site_url.rstrip('/')
        domain = re.search(r'(?:https?://)?(?:www\.)?([^/]+)', base_url)
        site_domain = domain.group(1) if domain else "unknown"

        # Get site-specific patterns
        site_patterns = None
        for site_key, patterns in JOB_SITE_PATTERNS.items():
            if site_key in site_domain:
                site_patterns = patterns
                break

        try:
            # Step 1: Navigate to job search page
            search_url = self._build_search_url(site_url, search_query, site_patterns)
            print(f"[Deep Scrape] Navigating to: {search_url}")

            await self.page.goto(search_url, wait_until="networkidle", timeout=45000)
            await asyncio.sleep(5)  # Wait longer for JS-heavy sites to load

            # Check for access denied/blocked pages
            page_title = await self.page.title()
            page_content = await self.page.content()
            if "access denied" in page_title.lower() or "access denied" in page_content.lower()[:2000]:
                print(f"[Deep Scrape] Site is blocking automated access - using fallback method")
                # Return with a note about using web search instead
                return {
                    "success": False,
                    "error": "Site blocks automated access (bot protection)",
                    "blocked": True,
                    "site": site_url,
                    "search_query": search_query,
                    "jobs": [],
                    "note": f"The site {site_domain} uses bot protection. Jobs will be found via web search instead."
                }

            # Scroll to trigger lazy loading
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3)")
            await asyncio.sleep(2)
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            await asyncio.sleep(2)

            # Step 2: Extract job listing URLs from search results
            job_links = await self._extract_job_links(site_patterns)
            print(f"[Deep Scrape] Found {len(job_links)} job links")

            if not job_links:
                # Try scrolling and retry
                await self._scroll_page()
                await asyncio.sleep(2)
                job_links = await self._extract_job_links(site_patterns)

            # Step 3: Visit each job page and extract details
            detail_selectors = JOB_DETAIL_SELECTORS.get(site_domain, JOB_DETAIL_SELECTORS["default"])

            for i, job_link in enumerate(job_links[:max_jobs]):
                if not job_link.get("url"):
                    continue

                job_url = job_link["url"]
                # Skip ad/tracking URLs
                if self._is_ad_url(job_url):
                    print(f"[Deep Scrape] Skipping ad URL: {job_url[:50]}...")
                    continue

                print(f"[Deep Scrape] Visiting job {i+1}: {job_url[:60]}...")

                try:
                    job_data = await self._scrape_single_job_page(
                        job_url,
                        job_link.get("title", ""),
                        detail_selectors
                    )
                    if job_data:
                        jobs.append(job_data)
                except Exception as e:
                    print(f"[Deep Scrape] Error scraping job page: {e}")
                    # Add basic info even if full scrape fails
                    jobs.append({
                        "title": job_link.get("title", "Unknown"),
                        "url": job_url,
                        "company": job_link.get("company", ""),
                        "requirements": ["Visit the job page for full details"],
                        "error": str(e)
                    })

                await asyncio.sleep(1)  # Be respectful, don't hammer the server

            return {
                "success": True,
                "type": "job_listings",
                "site": site_url,
                "search_query": search_query,
                "jobs_found": len(jobs),
                "jobs": jobs,
                "method": "deep_scrape"
            }

        except Exception as e:
            print(f"[Deep Scrape] Error: {e}")
            return {
                "success": False,
                "error": str(e),
                "jobs": jobs  # Return any jobs we managed to get
            }

    def _build_search_url(self, base_url: str, query: str, patterns: Dict = None) -> str:
        """Build a search URL for the job site."""
        if patterns and patterns.get("search_url"):
            return patterns["search_url"].format(query=quote_plus(query))

        # Generic search URL patterns
        domain = base_url.lower()
        encoded = quote_plus(query)

        if "gulftalent" in domain:
            return f"https://www.gulftalent.com/jobs?keywords={encoded}"
        elif "indeed" in domain:
            return f"https://www.indeed.com/jobs?q={encoded}"
        elif "linkedin" in domain:
            return f"https://www.linkedin.com/jobs/search/?keywords={encoded}"

        # Default: try common patterns
        return f"{base_url}/jobs?q={encoded}"

    def _is_ad_url(self, url: str) -> bool:
        """Check if URL is an ad/tracking URL."""
        ad_indicators = [
            'duckduckgo.com/y.js', 'bing.com/aclick', 'google.com/aclk',
            'ad.doubleclick', 'googleadservices', 'click.linksynergy',
            'ad_domain=', 'ad_provider=', 'ad_type=', 'click_metadata='
        ]
        url_lower = url.lower()
        return any(indicator in url_lower for indicator in ad_indicators)

    async def _extract_job_links(self, patterns: Dict = None) -> List[Dict]:
        """Extract job links from the search results page."""
        job_links = []
        patterns = patterns or DEFAULT_JOB_PATTERNS

        # Method 1: Try CSS selectors
        for selector in patterns.get("job_selectors", DEFAULT_JOB_PATTERNS["job_selectors"]):
            try:
                elements = await self.page.query_selector_all(selector)
                if not elements:
                    continue

                for element in elements[:20]:  # Check up to 20 elements
                    try:
                        # Get title
                        title = ""
                        title_sel = patterns.get("title_selector", "h2, h3, a")
                        for sel in title_sel.split(", "):
                            try:
                                title_el = await element.query_selector(sel)
                                if title_el:
                                    title = await title_el.inner_text()
                                    if title and len(title.strip()) > 3:
                                        break
                            except:
                                continue

                        # Get link - check if element itself is a link first
                        href = ""
                        tag_name = await element.evaluate("el => el.tagName")
                        if tag_name == "A":
                            href = await element.get_attribute("href")
                        if not href:
                            link_el = await element.query_selector("a[href]")
                            if link_el:
                                href = await link_el.get_attribute("href")
                                if not title:
                                    title = await link_el.inner_text()

                        if href and not href.startswith("http"):
                            href = self._make_absolute_url(href)

                        # Get company
                        company = ""
                        company_sel = patterns.get("company_selector", ".company")
                        for sel in company_sel.split(", "):
                            try:
                                company_el = await element.query_selector(sel)
                                if company_el:
                                    company = await company_el.inner_text()
                                    if company:
                                        break
                            except:
                                continue

                        if title and href and '/job' in href.lower():
                            job_links.append({
                                "title": title.strip()[:150],
                                "url": href,
                                "company": company.strip()[:100] if company else ""
                            })

                    except Exception as e:
                        continue

                if job_links:
                    break  # Found jobs with this selector

            except Exception as e:
                continue

        # Method 2: JavaScript fallback - find all job-like links on page
        if not job_links:
            print("[Deep Scrape] CSS selectors didn't work, trying JavaScript extraction...")
            try:
                # First, take a screenshot for debugging
                await self.page.screenshot(path="debug_job_search.png")
                print("[Deep Scrape] Screenshot saved to debug_job_search.png")

                js_links = await self.page.evaluate(r'''() => {
                    const links = [];
                    // Find all links that look like job postings
                    document.querySelectorAll('a[href]').forEach(a => {
                        const href = a.href;
                        const text = a.innerText.trim();
                        // Check if it looks like a job link
                        if (href && text && text.length > 5 && text.length < 200) {
                            // Job indicators in URL - expanded patterns
                            const isJobUrl = /job|vacancy|career|position|opening|posting|employment/i.test(href);
                            // Skip common non-job links
                            const isNavLink = /login|signup|register|about-us|contact-us|privacy|terms|cookie|search\?|filter|footer|header|menu|nav|social|facebook|twitter|linkedin\.com|instagram/i.test(href);
                            if (isJobUrl && !isNavLink) {
                                links.push({
                                    title: text.split('\n')[0].trim(),
                                    url: href,
                                    company: ''
                                });
                            }
                        }
                    });
                    return links.slice(0, 20);
                }''')
                if js_links:
                    job_links = js_links
                    print(f"[Deep Scrape] JavaScript found {len(job_links)} job links")
            except Exception as e:
                print(f"[Deep Scrape] JavaScript extraction failed: {e}")

        # Method 3: Last resort - find any significant links
        if not job_links:
            print("[Deep Scrape] Trying last resort link extraction...")
            try:
                # Debug: Print page info
                page_title = await self.page.title()
                page_url = self.page.url
                print(f"[Deep Scrape] Page title: {page_title}")
                print(f"[Deep Scrape] Current URL: {page_url}")

                # Get total link count for debugging
                link_count = await self.page.evaluate("document.querySelectorAll('a').length")
                print(f"[Deep Scrape] Total links on page: {link_count}")

                all_links = await self.page.evaluate(r'''() => {
                    const links = [];
                    document.querySelectorAll('a[href]').forEach(a => {
                        const href = a.href;
                        const text = a.innerText.trim();
                        // Get links with decent text that aren't navigation
                        if (href && text && text.length > 10 && text.length < 150) {
                            const isNav = /^(home|about|contact|login|sign|menu|nav|cookie|privacy|terms)/i.test(text);
                            if (!isNav && !href.includes('#') && !href.includes('javascript:')) {
                                links.push({
                                    title: text,
                                    url: href,
                                    company: ''
                                });
                            }
                        }
                    });
                    return links.slice(0, 15);
                }''')
                if all_links:
                    job_links = all_links
                    print(f"[Deep Scrape] Found {len(job_links)} potential links")
            except Exception as e:
                print(f"[Deep Scrape] Last resort failed: {e}")

        return job_links

    async def _scrape_single_job_page(
        self,
        job_url: str,
        fallback_title: str,
        selectors: Dict
    ) -> Optional[Dict]:
        """Visit a single job page and extract detailed information."""
        try:
            await self.page.goto(job_url, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(2)  # Wait for content

            # Extract title
            title = fallback_title
            for sel in selectors.get("title", "h1").split(", "):
                try:
                    el = await self.page.query_selector(sel)
                    if el:
                        text = await el.inner_text()
                        if text and len(text.strip()) > 3:
                            title = text.strip()
                            break
                except:
                    continue

            # Extract company
            company = ""
            for sel in selectors.get("company", ".company").split(", "):
                try:
                    el = await self.page.query_selector(sel)
                    if el:
                        text = await el.inner_text()
                        if text:
                            company = text.strip()
                            break
                except:
                    continue

            # Extract location
            location = ""
            for sel in selectors.get("location", ".location").split(", "):
                try:
                    el = await self.page.query_selector(sel)
                    if el:
                        text = await el.inner_text()
                        if text:
                            location = text.strip()
                            break
                except:
                    continue

            # Extract requirements/description - this is the main content
            requirements = []
            req_selectors = selectors.get("requirements", [".description"])

            for sel in req_selectors:
                try:
                    el = await self.page.query_selector(sel)
                    if el:
                        full_text = await el.inner_text()
                        if full_text and len(full_text.strip()) > 50:
                            # Parse the text to extract bullet points/requirements
                            requirements = self._parse_requirements_text(full_text)
                            if requirements:
                                break
                except:
                    continue

            # If still no requirements, try to get any main content
            if not requirements:
                try:
                    main_content = await self.page.query_selector("main, article, .content, #content")
                    if main_content:
                        text = await main_content.inner_text()
                        requirements = self._parse_requirements_text(text)
                except:
                    pass

            # Extract salary if available
            salary = ""
            for sel in selectors.get("salary", ".salary").split(", "):
                try:
                    el = await self.page.query_selector(sel)
                    if el:
                        text = await el.inner_text()
                        if text:
                            salary = text.strip()
                            break
                except:
                    continue

            # Decode HTML entities in title
            title = self._decode_html_entities(title)

            return {
                "title": title[:200],
                "url": job_url,
                "company": company[:100] if company else "",
                "location": location[:100] if location else "",
                "requirements": requirements[:15],  # Max 15 requirements
                "salary": salary[:50] if salary else "",
                "scraped_from_detail_page": True
            }

        except Exception as e:
            print(f"[Deep Scrape] Error on job page {job_url}: {e}")
            return None

    def _parse_requirements_text(self, text: str) -> List[str]:
        """Parse job description text to extract requirements."""
        if not text:
            return []

        requirements = []

        # Split by common separators
        lines = re.split(r'[\n\r•●○◦▪▸►→\-\*]', text)

        for line in lines:
            cleaned = line.strip()
            # Skip if too short or too long
            if len(cleaned) < 10 or len(cleaned) > 300:
                continue
            # Skip common noise
            if any(skip in cleaned.lower() for skip in [
                'click here', 'apply now', 'submit', 'cookie', 'privacy',
                'terms of', 'all rights', 'copyright', 'follow us'
            ]):
                continue
            # Check if it looks like a requirement
            if any(indicator in cleaned.lower() for indicator in [
                'experience', 'skill', 'knowledge', 'ability', 'degree',
                'proficient', 'familiar', 'understanding', 'years', 'required',
                'bachelor', 'master', 'certification', 'strong', 'excellent',
                'proven', 'ability to', 'responsible', 'develop', 'manage'
            ]):
                requirements.append(cleaned)

        # If we found very few requirements, just take first meaningful paragraphs
        if len(requirements) < 3:
            paragraphs = text.split('\n\n')
            for para in paragraphs[:5]:
                cleaned = para.strip()
                if 50 < len(cleaned) < 500:
                    if cleaned not in requirements:
                        requirements.append(cleaned)

        return requirements[:15]

    def _decode_html_entities(self, text: str) -> str:
        """Decode HTML entities like &amp; to &."""
        import html
        return html.unescape(text) if text else ""


# Singleton instance
_browser_skill: Optional[BrowserAutomationSkill] = None


async def get_browser_skill() -> BrowserAutomationSkill:
    """Get the singleton browser automation skill."""
    global _browser_skill
    if _browser_skill is None:
        _browser_skill = BrowserAutomationSkill()
    return _browser_skill


async def browse_with_playwright(url: str, intent: str, search_terms: List[str] = None) -> Dict[str, Any]:
    """Convenience function to browse with Playwright."""
    skill = await get_browser_skill()
    try:
        result = await skill.browse_and_extract(url, intent, search_terms)
        return result
    finally:
        await skill.close()
