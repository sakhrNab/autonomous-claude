# MCP Orchestrator Usage Guide

## Overview

The MCP Orchestrator is an intelligent autonomous operator that can:
- Scrape websites for content
- Search the web (requires API keys)
- Execute complex multi-step tasks
- Use Claude AI for intelligent reasoning

## Current Status

### What Works
- **Web Scraping**: Scrape headlines, content from any website
  - Example: "Scrape headlines from bbc.com"
  - Uses: httpx + Claude CLI for extraction

### What Needs Configuration
- **Web Search**: DuckDuckGo blocks automated requests
  - Solution: Configure Brave Search MCP with API key
  - Set `BRAVE_API_KEY` environment variable

## Usage Examples

### 1. As Standalone Application

```bash
# Start the server
cd mcp-orchestrator
python api/server.py

# Access UI at http://localhost:8000
```

### 2. Via API

```bash
# Submit a task
curl -X POST http://localhost:8000/api/task \
  -H "Content-Type: application/json" \
  -d '{"intent": "scrape headlines from bbc.com"}'

# Check task status
curl http://localhost:8000/api/tasks/{task_id}
```

### 3. Future: As Python Library (Planned)

```python
from mcp_orchestrator import Orchestrator

# Initialize with your project
orchestrator = Orchestrator(
    project_path="/path/to/your/project"
)

# Analyze your codebase
await orchestrator.analyze_project()

# Execute development tasks
result = await orchestrator.run("Add user authentication")
result = await orchestrator.run("Create REST API for users")
result = await orchestrator.run("Write tests for user module")
```

## Slash Commands (Planned)

Direct agent routing:
- `/code <task>` - Route directly to code agent
- `/search <query>` - Route to search capability
- `/scrape <url>` - Route to scraping capability
- `/plan <task>` - Create execution plan only

## Integration in Your Projects

### Step 1: Clone/Install

```bash
# Clone the repository
git clone <repo-url> mcp-orchestrator

# Install dependencies
cd mcp-orchestrator
pip install -r requirements.txt
```

### Step 2: Configure

```bash
# Set environment variables
export BRAVE_API_KEY="your-key"  # For web search
export FIRECRAWL_URL="http://localhost:3002"  # For advanced scraping

# Or start Firecrawl locally (no API key needed)
docker run -p 3002:3002 mendableai/firecrawl
```

### Step 3: Start Server

```bash
python api/server.py
```

### Step 4: Submit Tasks via API

```python
import httpx

async def use_orchestrator(task: str):
    async with httpx.AsyncClient() as client:
        # Submit task
        response = await client.post(
            "http://localhost:8000/api/task",
            json={"intent": task}
        )
        task_id = response.json()["task_id"]

        # Poll for completion
        while True:
            status = await client.get(f"http://localhost:8000/api/tasks/{task_id}")
            result = status.json()
            if result["state"] == "completed":
                return result["result"]
            await asyncio.sleep(1)
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User Request                          │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                  Planning Agent                          │
│   - Analyzes intent                                     │
│   - Creates execution plan                              │
│   - Routes to appropriate capability                    │
└─────────────────────────────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │  Code    │    │  Search  │    │  Scrape  │
    │  Agent   │    │  Skill   │    │  Skill   │
    └──────────┘    └──────────┘    └──────────┘
           │               │               │
           ▼               ▼               ▼
┌─────────────────────────────────────────────────────────┐
│               Capability Resolver                        │
│   - Discovers installed MCPs                            │
│   - Prioritizes: Firecrawl > Universal > HTTP           │
│   - Falls back gracefully                               │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    Claude CLI                            │
│   - Uses your Claude subscription                       │
│   - Intelligent content extraction                      │
│   - No separate API key needed                          │
└─────────────────────────────────────────────────────────┘
```

## Known Limitations

1. **Web Search Blocked**: DuckDuckGo shows CAPTCHA for bots
   - Solution: Use Brave Search API

2. **Python 3.13 + Windows**: Playwright asyncio issues
   - Solution: Use httpx + Claude instead

3. **Large Pages**: Windows command line limit (~8KB)
   - Solution: Content is truncated to 4KB for extraction

## Roadmap

- [ ] Package as pip-installable library
- [ ] Add slash commands for direct routing
- [ ] Implement agent chaining (fallback when one fails)
- [ ] Add AI connection caching
- [ ] Support Brave Search MCP integration
