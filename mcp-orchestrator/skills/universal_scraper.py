"""
Universal Intelligent Scraper

Uses Claude AI to intelligently extract data from ANY website.
No hardcoded patterns - pure AI understanding of page structure.

IMPORTANT: Uses synchronous Playwright (sync_api) to avoid Python 3.13 Windows
asyncio subprocess issues. Runs in thread pool for async compatibility.
"""

import asyncio
import json
import re
import subprocess
import shutil
import os
import sys
import httpx
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor


# Sites with known APIs (preferred - no scraping needed!)
SITES_WITH_API = {
    "remoteok.com": {
        "api_url": "https://remoteok.com/api",
        "type": "json_array",
    },
}

# Sites that are known to work well for HTML scraping
WORKING_JOB_SITES = {
    "remoteok.com": {
        "search_url": "https://remoteok.com",  # Main page has all jobs
        "has_api": True,
    },
    "weworkremotely.com": {
        "search_url": "https://weworkremotely.com/remote-jobs/search?term={query}",
    },
    "workingnomads.com": {
        "search_url": "https://www.workingnomads.com/jobs?category=development",
    },
    "startup.jobs": {
        "search_url": "https://startup.jobs/?q={query}",
    },
}

# Thread pool for running sync playwright
_executor = ThreadPoolExecutor(max_workers=2)


class UniversalScraper:
    """
    Intelligent scraper that uses Claude to understand and extract data from any page.
    Uses httpx for fast HTTP requests and Claude for intelligent extraction.
    """

    def __init__(self):
        self._initialized = False
        self._http_client = None

    async def initialize(self) -> bool:
        """Initialize HTTP client."""
        try:
            self._http_client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                }
            )
            self._initialized = True
            print("[UniversalScraper] Initialized with httpx")
            return True
        except Exception as e:
            print(f"[UniversalScraper] Init error: {e}")
            return False

    async def close(self):
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
        self._initialized = False

    async def scrape_with_claude(
        self,
        url: str,
        user_intent: str,
        requested_fields: List[str] = None
    ) -> Dict[str, Any]:
        """
        Use Claude to intelligently extract data from a page.

        Uses httpx for HTTP requests and Claude for intelligent extraction.
        """
        if not self._initialized:
            if not await self.initialize():
                return {"success": False, "error": "Failed to initialize"}

        try:
            print(f"[UniversalScraper] Fetching: {url}")
            response = await self._http_client.get(url)

            # Check for blocking/errors
            if response.status_code == 403:
                return {"success": False, "error": "Site blocked (403 Forbidden)", "blocked": True}
            if response.status_code == 503:
                return {"success": False, "error": "Site blocked (503)", "blocked": True}
            if response.status_code != 200:
                return {"success": False, "error": f"HTTP {response.status_code}"}

            page_html = response.text

            # Check for access denied in content
            if "access denied" in page_html.lower()[:2000]:
                return {"success": False, "error": "Site blocked", "blocked": True}

            # Extract text from HTML
            page_text = self._html_to_text(page_html)

            # Extract title
            title = ""
            title_match = re.search(r'<title[^>]*>([^<]+)</title>', page_html, re.IGNORECASE)
            if title_match:
                title = title_match.group(1).strip()

            # Get structured data if available (JSON-LD)
            structured_data = self._extract_structured_data_from_html(page_html)

            # Use Claude to extract - limit text for Windows command line (~8KB limit)
            result = await self._claude_extract(
                page_text[:4000],  # Limit to 4KB for Windows CLI
                page_html[:8000],  # HTML for structure
                structured_data,
                user_intent,
                requested_fields or ["title", "content", "headlines", "summary"]
            )

            result["url"] = url
            result["source_title"] = title
            return result

        except httpx.TimeoutException:
            print(f"[UniversalScraper] Timeout: {url}")
            return {"success": False, "error": "Request timeout"}
        except Exception as e:
            print(f"[UniversalScraper] Error: {e}")
            return {"success": False, "error": str(e)}

    def _html_to_text(self, html: str) -> str:
        """Convert HTML to plain text."""
        import html as html_module
        # Remove scripts and styles
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        # Remove tags
        text = re.sub(r'<[^>]+>', ' ', text)
        # Decode entities
        text = html_module.unescape(text)
        # Clean whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _extract_structured_data_from_html(self, html: str) -> Dict:
        """Extract JSON-LD structured data from HTML."""
        data = {"jsonld": [], "meta": {}}

        # JSON-LD
        jsonld_pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
        matches = re.findall(jsonld_pattern, html, re.DOTALL | re.IGNORECASE)
        for match in matches:
            try:
                data["jsonld"].append(json.loads(match))
            except:
                pass

        # Meta tags
        meta_pattern = r'<meta[^>]*(?:property|name)=["\']([^"\']+)["\'][^>]*content=["\']([^"\']+)["\']'
        for name, content in re.findall(meta_pattern, html, re.IGNORECASE):
            data["meta"][name] = content

        return data


    async def _claude_extract(
        self,
        page_text: str,
        page_html: str,
        structured_data: Dict,
        user_intent: str,
        requested_fields: List[str]
    ) -> Dict[str, Any]:
        """Use Claude CLI to intelligently extract data."""

        claude_path = shutil.which("claude")
        if not claude_path:
            print("[UniversalScraper] Claude CLI not found, using fallback")
            return self._fallback_extract(page_text, requested_fields)

        fields_str = ", ".join(requested_fields)

        # Limit page text to avoid Windows command line limits (~8191 chars)
        max_text_size = 5000  # ~5KB of page text - safe for Windows
        truncated_text = page_text[:max_text_size]

        # Detect content type from intent and page
        intent_lower = user_intent.lower()
        is_job_related = any(kw in intent_lower for kw in ['job', 'jobs', 'career', 'hiring', 'position'])
        is_news = any(kw in intent_lower for kw in ['news', 'headline', 'article', 'story'])

        if is_job_related:
            prompt = f"""Extract job postings from this page.

FIELDS: {fields_str}

PAGE:
{truncated_text}

Return ONLY JSON array:
[{{"title": "...", "company": "...", "skills": ["..."], "salary": "..."}}]"""
        elif is_news:
            # Very simple prompt for headline extraction
            # Take only first 2000 chars to be safe
            short_text = truncated_text[:2000].replace('"', "'").replace('\n', ' ')
            prompt = f'Extract headlines from: {short_text}. Return JSON: [{{"title":"headline"}}]'
        else:
            # General extraction
            prompt = f"""Extract the requested information from this page.

USER REQUEST: {user_intent}
FIELDS: {fields_str}

PAGE:
{truncated_text}

Return ONLY JSON with extracted data:
{{"content": "main content", "data": [...], "summary": "brief summary"}}"""

        print(f"[UniversalScraper] Sending {len(prompt)} chars to Claude CLI")

        try:
            # Truncate more aggressively for Windows command line limits
            # Windows has ~8191 char limit for cmd.exe
            max_prompt_size = 6000
            if len(prompt) > max_prompt_size:
                # Extract just the page text portion and truncate it
                prompt_parts = prompt.split("PAGE CONTENT:")
                if len(prompt_parts) == 2:
                    header = prompt_parts[0] + "PAGE CONTENT:\n"
                    content_and_footer = prompt_parts[1]
                    # Find where instructions start
                    instr_idx = content_and_footer.find("INSTRUCTIONS:")
                    if instr_idx > 0:
                        footer = content_and_footer[instr_idx:]
                        content = content_and_footer[:instr_idx]
                        # Truncate content to fit
                        max_content = max_prompt_size - len(header) - len(footer) - 100
                        content = content[:max_content] + "\n...[truncated]...\n"
                        prompt = header + content + footer
                    else:
                        prompt = prompt[:max_prompt_size]
                else:
                    prompt = prompt[:max_prompt_size]
                print(f"[UniversalScraper] Truncated prompt to {len(prompt)} chars")

            result = subprocess.run(
                [claude_path, "-p", prompt, "--output-format", "text"],
                capture_output=True,
                text=True,
                timeout=120,
                env={**os.environ, "TERM": "dumb"}
            )

            response = result.stdout.strip()
            if result.stderr:
                print(f"[UniversalScraper] Claude stderr: {result.stderr[:200]}")
            print(f"[UniversalScraper] Claude response: {len(response)} chars")

            # Parse JSON
            json_match = re.search(r'[\[\{][\s\S]*[\]\}]', response)
            if json_match:
                data = json.loads(json_match.group())
                # Return in a general format
                if isinstance(data, list):
                    return {"success": True, "data": data, "items": data, "method": "claude_intelligent"}
                else:
                    return {"success": True, "data": data, "items": [data], "method": "claude_intelligent"}
            else:
                print(f"[UniversalScraper] No JSON in response: {response[:200]}")
                # Return raw response if no JSON
                if response:
                    return {"success": True, "data": {"content": response}, "method": "claude_raw"}
                return self._fallback_extract(page_text, requested_fields)

        except subprocess.TimeoutExpired:
            print("[UniversalScraper] Claude timeout")
            return self._fallback_extract(page_text, requested_fields)
        except json.JSONDecodeError as e:
            print(f"[UniversalScraper] JSON error: {e}")
            return self._fallback_extract(page_text, requested_fields)
        except Exception as e:
            print(f"[UniversalScraper] Claude error: {e}")
            return self._fallback_extract(page_text, requested_fields)

    def _fallback_extract(self, text: str, fields: List[str]) -> Dict[str, Any]:
        """Fallback regex-based extraction when Claude fails."""
        jobs = []

        # Simple pattern matching
        # Look for job-like sections
        sections = re.split(r'\n{2,}', text)

        current_job = {}
        for section in sections:
            # Skip short sections
            if len(section) < 50:
                continue

            # Look for title-like text (capitalized, not too long)
            lines = section.strip().split('\n')
            if lines:
                first_line = lines[0].strip()
                if 20 < len(first_line) < 100 and not first_line.startswith('http'):
                    if current_job and current_job.get('title'):
                        jobs.append(current_job)
                        current_job = {}
                    current_job['title'] = first_line

            # Look for company
            company_match = re.search(r'(?:at|by|@)\s+([A-Z][a-zA-Z\s]+)', section)
            if company_match and 'company' not in current_job:
                current_job['company'] = company_match.group(1).strip()

            # Look for salary
            salary_match = re.search(r'\$[\d,]+(?:\s*[-–]\s*\$[\d,]+)?(?:\s*(?:k|K|/yr|/year|per year))?', section)
            if salary_match:
                current_job['salary'] = salary_match.group(0)

            # Look for skills
            skills = re.findall(r'\b(Python|Java|JavaScript|React|Node|AWS|Docker|Kubernetes|SQL|TypeScript|Go|Rust|C\+\+|Ruby|PHP)\b', section, re.IGNORECASE)
            if skills:
                current_job['skills'] = list(set(s.title() for s in skills))

        if current_job and current_job.get('title'):
            jobs.append(current_job)

        return {"success": True, "jobs": jobs[:10], "method": "fallback_regex"}

    async def fetch_from_api(
        self,
        site: str,
        query: str,
        requested_fields: List[str],
        max_jobs: int = 10
    ) -> Optional[Dict[str, Any]]:
        """Fetch jobs directly from API if site has one."""
        api_config = None
        for site_key, config in SITES_WITH_API.items():
            if site_key in site.lower():
                api_config = config
                break

        if not api_config:
            return None

        try:
            print(f"[UniversalScraper] Fetching from API: {api_config['api_url']}")
            response = await self._http_client.get(api_config['api_url'])

            if response.status_code != 200:
                print(f"[UniversalScraper] API returned {response.status_code}")
                return None

            data = response.json()

            # Process based on API type
            if api_config['type'] == 'json_array':
                # RemoteOK format - array of jobs, first element is metadata
                jobs = []
                query_terms = query.lower().split()

                for item in data[1:]:  # Skip first element (metadata)
                    if not isinstance(item, dict):
                        continue

                    # Filter by query terms
                    position = item.get('position', '').lower()
                    tags = ' '.join(item.get('tags', [])).lower()
                    if query_terms and not any(term in position or term in tags for term in query_terms):
                        continue

                    # Extract salary from description or dedicated field
                    salary = item.get('salary', '')
                    if not salary:
                        desc = item.get('description', '')
                        salary_match = re.search(r'\$[\d,]+(?:k|K)?(?:\s*[-–]\s*\$[\d,]+(?:k|K)?)?(?:\s*/\s*(?:yr|year))?', desc)
                        if salary_match:
                            salary = salary_match.group(0)

                    # Extract skills from tags and description
                    skills = item.get('tags', [])

                    job = {
                        'title': item.get('position', 'Unknown'),
                        'company': item.get('company', 'Unknown'),
                        'url': f"https://remoteok.com/remote-jobs/{item.get('id', '')}",
                        'location': item.get('location', 'Remote'),
                        'salary': salary or None,
                        'skills': skills,
                        'description': self._clean_html(item.get('description', ''))[:500],
                        'date_posted': item.get('date', ''),
                    }

                    # Add requirements if requested
                    if 'requirements' in requested_fields:
                        # Extract requirements from description
                        desc = self._clean_html(item.get('description', ''))
                        requirements = self._extract_requirements_from_text(desc)
                        job['requirements'] = requirements

                    jobs.append(job)

                    if len(jobs) >= max_jobs:
                        break

                if jobs:
                    return {
                        'success': True,
                        'jobs': jobs,
                        'total_found': len(data) - 1,
                        'method': 'api_direct',
                        'source': api_config['api_url']
                    }

        except Exception as e:
            print(f"[UniversalScraper] API error: {e}")

        return None

    def _clean_html(self, html: str) -> str:
        """Remove HTML tags from text."""
        import html as html_module
        text = re.sub(r'<[^>]+>', ' ', html)
        text = html_module.unescape(text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _extract_requirements_from_text(self, text: str) -> List[str]:
        """Extract requirement-like sentences from text."""
        requirements = []
        sentences = re.split(r'[.•\n]', text)
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 20 or len(sentence) > 300:
                continue
            if any(kw in sentence.lower() for kw in [
                'experience', 'degree', 'bachelor', 'master', 'knowledge',
                'proficiency', 'skill', 'ability', 'required', 'must',
                'years', 'familiar', 'understanding', 'certification',
                'strong', 'excellent', 'proven', 'demonstrated'
            ]):
                requirements.append(sentence)
                if len(requirements) >= 10:
                    break
        return requirements

    async def scrape_jobs(
        self,
        site: str,
        query: str,
        user_intent: str,
        requested_fields: List[str] = None,
        max_jobs: int = 10
    ) -> Dict[str, Any]:
        """
        Fetch jobs from a site - tries API first, then HTML scraping.
        """
        if not self._initialized:
            if not await self.initialize():
                return {"success": False, "error": "Failed to initialize"}

        requested_fields = requested_fields or ['title', 'company', 'url', 'skills', 'salary']

        # STEP 1: Try API first (much more reliable!)
        api_result = await self.fetch_from_api(site, query, requested_fields, max_jobs)
        if api_result and api_result.get('jobs'):
            print(f"[UniversalScraper] Got {len(api_result['jobs'])} jobs from API!")
            return api_result

        # STEP 2: Fall back to HTML scraping
        site_config = None
        for site_key, config in WORKING_JOB_SITES.items():
            if site_key in site.lower():
                site_config = config
                break

        # Build URL
        if site_config:
            url = site_config.get("search_url", site)
            if '{query}' in url:
                url = url.format(query=query.replace(" ", "-"))
        else:
            url = site

        print(f"[UniversalScraper] Scraping HTML: {url}")

        # Scrape and extract
        result = await self.scrape_with_claude(
            url=url,
            user_intent=user_intent,
            requested_fields=requested_fields
        )

        if result.get("success") and result.get("jobs"):
            jobs = result["jobs"][:max_jobs]

            # Clean up jobs - ensure all requested fields exist
            for job in jobs:
                for field in (requested_fields or []):
                    if field not in job:
                        job[field] = None
                job["source_url"] = url

            return {
                "success": True,
                "jobs": jobs,
                "total_found": len(result["jobs"]),
                "method": result.get("method", "unknown"),
                "source": url
            }

        return result

    async def scrape_intelligent(
        self,
        url: str,
        user_intent: str,
        requested_fields: List[str] = None
    ) -> Dict[str, Any]:
        """
        GENERAL-PURPOSE intelligent scraping - not just for jobs!

        Uses Claude to understand what the user wants and extract it from any page.
        This is the method the capability resolver uses.
        """
        if not self._initialized:
            await self.initialize()

        if not url:
            return {"success": False, "error": "No URL provided"}

        requested_fields = requested_fields or []

        # Determine what kind of content this is based on intent
        intent_lower = user_intent.lower()

        # If it's a job-related request, use the specialized method
        if any(kw in intent_lower for kw in ['job', 'jobs', 'career', 'hiring', 'position', 'vacancy']):
            return await self.scrape_jobs(
                site=url,
                query=' '.join(self._extract_search_terms(user_intent)),
                user_intent=user_intent,
                requested_fields=requested_fields,
            )

        # For general scraping, use Claude-powered extraction
        try:
            result = await self.scrape_with_claude(
                url=url,
                user_intent=user_intent,
                requested_fields=requested_fields,
            )

            if result.get("success"):
                return {
                    "success": True,
                    "url": url,
                    "content": result.get("extracted_data", result.get("data", {})),
                    "method": result.get("method", "claude_intelligent"),
                    "raw_html_length": result.get("raw_html_length", 0),
                }
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e), "url": url}

    def _extract_search_terms(self, intent: str) -> List[str]:
        """Extract search terms from intent."""
        intent_lower = intent.lower()
        skip_words = {
            'scrape', 'from', 'and', 'the', 'give', 'me', 'their', 'find',
            'search', 'get', 'latest', 'jobs', 'requirements', 'https', 'http',
            'www', 'com', 'job', 'with', 'for', 'this', 'that', 'what', 'where',
            'please', 'can', 'you', 'need', 'want', 'look', 'looking', 'show', 'list'
        }
        words = intent_lower.split()
        terms = [
            w for w in words
            if len(w) > 3
            and w not in skip_words
            and not w.startswith('http')
            and '.' not in w
        ]
        return terms[:5]


# Singleton instance
_scraper_instance = None

async def get_universal_scraper() -> UniversalScraper:
    """Get or create singleton scraper instance."""
    global _scraper_instance
    if _scraper_instance is None:
        _scraper_instance = UniversalScraper()
    return _scraper_instance
