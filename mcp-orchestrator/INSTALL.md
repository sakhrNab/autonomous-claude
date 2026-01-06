# MCP Orchestrator - Installation & Usage Guide

## How It Works

This project is a **Python package** that can be installed system-wide using `pip`. Once installed, you can import and use it from any Python project on your computer.

The magic happens through `pyproject.toml` - this file tells pip how to install the package and where to find the code.

---

## Installation on Any Computer

### Step 1: Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/mcp-orchestrator.git
cd mcp-orchestrator
```

### Step 2: Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browsers (for web scraping)
playwright install chromium
```

### Step 3: Install the SDK Package

Choose one method:

```bash
# Option A: Editable install (recommended for development)
# Changes to source code take effect immediately
pip install -e .

# Option B: Regular install (for production use)
pip install .
```

### Step 4: Verify Installation

```bash
# Test from any directory
cd ~
python -c "from mcp_orchestrator import Orchestrator; print('SUCCESS')"
```

---

## Usage

### Method 1: Start Server + Use SDK

**Terminal 1 - Start the server:**
```bash
cd /path/to/mcp-orchestrator
python api/server.py
# Server runs at http://localhost:8000
```

**Terminal 2 - Use from any project:**
```python
from mcp_orchestrator import Orchestrator

import asyncio

async def main():
    # Connect to running server
    orchestrator = Orchestrator(server_url="http://localhost:8000")

    # Run any task
    result = await orchestrator.run("Scrape headlines from bbc.com")
    print(result)

asyncio.run(main())
```

### Method 2: Auto-Start Server

```python
from mcp_orchestrator import Orchestrator

orchestrator = Orchestrator(
    project_path="/path/to/your/project",
    server_url="http://localhost:8000",
    auto_start_server=True  # Starts server automatically if not running
)

result = await orchestrator.run("Add user authentication")
```

### Method 3: Synchronous Usage (Simpler)

```python
from mcp_orchestrator import SyncOrchestrator

# No async/await needed
orchestrator = SyncOrchestrator(server_url="http://localhost:8000")
result = orchestrator.run("Build a login page")
print(result)
```

---

## Available Methods

```python
from mcp_orchestrator import Orchestrator

orchestrator = Orchestrator(server_url="http://localhost:8000")

# General task execution
await orchestrator.run("Any natural language task")

# Specific agent shortcuts
await orchestrator.code("Fix the login bug")           # Code agent
await orchestrator.api("Create REST endpoint /users")  # API agent
await orchestrator.db("Add user table migration")      # Database agent
await orchestrator.test("Run all unit tests")          # Test agent
await orchestrator.scrape("bbc.com")                   # Web scraper
await orchestrator.search("latest AI news")            # Web search
await orchestrator.plan("Design auth system")          # Get execution plan

# Project analysis
analysis = await orchestrator.analyze_project()
print(analysis["languages"])   # ['py', 'ts', 'js']
print(analysis["frameworks"])  # ['python', 'node']
```

---

## Creating Custom Agents, Skills, and Hooks

```python
from mcp_orchestrator import Agent, Skill, Hook

# Create custom agent
my_agent = Agent(
    name="data-processor",
    description="Processes and transforms data files",
    tools=["Read", "Write", "Bash"],
    priority=85
)
my_agent.save()  # Saves to .claude/agents/data-processor.md

# Create custom skill
my_skill = Skill(
    name="csv-parser",
    description="Parse and analyze CSV files",
    tools=["Read", "Bash"],
    instructions="Parse CSV files and extract insights..."
)
my_skill.save()  # Saves to .claude/skills/csv-parser/SKILL.md

# Create hook
my_hook = Hook(
    event="PostToolUse",
    matcher="Write|Edit",
    command="prettier --write $FILE"
)
```

---

## Environment Variables

```bash
# Optional: For web search functionality
export BRAVE_API_KEY=your_brave_search_api_key

# Optional: Custom server port
export MCP_SERVER_PORT=8000
```

---

## Project Structure After Installation

```
mcp-orchestrator/           # Clone this repo
├── pyproject.toml          # Package configuration (pip reads this)
├── mcp_orchestrator/       # The SDK package (gets installed)
│   ├── __init__.py
│   ├── orchestrator.py     # Main Orchestrator class
│   ├── agents.py           # Agent definitions
│   ├── skills.py           # Skill definitions
│   └── hooks.py            # Hook definitions
├── api/
│   └── server.py           # FastAPI server
├── core/                   # Core logic
├── .claude/                # Claude Code compatible config
│   ├── agents/             # Agent definitions (.md files)
│   ├── skills/             # Skill definitions (SKILL.md)
│   └── hooks/              # Hook configuration (hooks.json)
└── requirements.txt
```

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'mcp_orchestrator'"

```bash
# Make sure you installed it
pip install -e /path/to/mcp-orchestrator

# Check it's installed
pip show mcp-orchestrator
```

### "Server not running"

```bash
# Start the server first
cd /path/to/mcp-orchestrator
python api/server.py
```

### Different Python versions

```bash
# If you have multiple Python versions, use the same one for install and run
python3 -m pip install -e .
python3 -c "from mcp_orchestrator import Orchestrator; print('OK')"
```

---

## Quick Start Example

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/mcp-orchestrator.git
cd mcp-orchestrator

# 2. Install
pip install -r requirements.txt
pip install -e .
playwright install chromium

# 3. Start server (in background or separate terminal)
python api/server.py &

# 4. Use it
python -c "
from mcp_orchestrator import SyncOrchestrator
o = SyncOrchestrator()
print(o.run('Scrape headlines from bbc.com'))
"
```

---

## Use in Your Own Project

```bash
# In your project directory
cd ~/my-awesome-project

# Create a script
cat > test_orchestrator.py << 'EOF'
from mcp_orchestrator import Orchestrator
import asyncio

async def main():
    orchestrator = Orchestrator(
        project_path=".",
        server_url="http://localhost:8000"
    )

    # Analyze your project
    analysis = await orchestrator.analyze_project()
    print(f"Found {len(analysis['files'])} files")

    # Run a task
    result = await orchestrator.run("Explain the project structure")
    print(result)

asyncio.run(main())
EOF

# Run it
python test_orchestrator.py
```

That's it! The SDK is now available system-wide on your computer.
