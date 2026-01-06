# MCP Orchestrator

**Universal agents, hooks, skills, and plugins for Claude Code.**

Install once, use in any project. No Anthropic API key needed - uses your Claude Code subscription.

## What's Included

| Component | Count | Purpose |
|-----------|-------|---------|
| **Agents** | 15 | Specialized AI assistants for different tasks |
| **Skills** | 9 | Reusable capabilities and patterns |
| **Hooks** | 5 | Automatic behaviors on events |
| **Plugins** | 1 | Ralph Wiggum iteration pattern |

### Key Features

- **Commit Protection** - `git commit/push` blocked until you explicitly ask
- **Activity Logging** - All actions logged to `.claude/activity.log`
- **Ralph Wiggum** - Iterate until task is complete
- **No API Key** - Works with Claude Code subscription

---

## Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/mcp-orchestrator.git
cd mcp-orchestrator
```

### Step 2: Install the Package

```bash
pip install -e .
```

This installs `mcp_orchestrator` as a Python package you can import anywhere.

### Step 3: Verify Installation

```bash
python -c "from mcp_orchestrator import setup_project; print('SUCCESS')"
```

---

## Usage in Your Projects

### Option A: Python Setup (Recommended)

```bash
cd /path/to/your/project

python -c "from mcp_orchestrator import setup_project; setup_project('.')"
```

### Option B: CLI Setup

```bash
cd /path/to/your/project
mcp-setup .
```

### Option C: Manual Copy

```bash
cp -r /path/to/mcp-orchestrator/.claude /path/to/your/project/
```

### What Gets Created

```
your-project/
└── .claude/
    ├── agents/              # 15 agent definitions
    │   ├── planning-agent.md
    │   ├── code-agent.md
    │   ├── api-agent.md
    │   └── ...
    ├── skills/              # 9 skill definitions
    │   ├── tdd/SKILL.md
    │   ├── code-review/SKILL.md
    │   └── ...
    ├── hooks/
    │   └── hooks.json       # Event hooks
    ├── plugins/
    │   └── ralph-wiggum/    # Iteration plugin
    └── settings.json        # Permissions
```

### Use Claude Code

```bash
cd /path/to/your/project
claude
```

Claude Code automatically finds and uses the agents, skills, and hooks!

---

## Available Agents

| Agent | Command | Purpose |
|-------|---------|---------|
| `planning-agent` | (auto) | Analyzes tasks, creates plans, delegates |
| `code-agent` | `/code` | Writes and modifies code |
| `api-agent` | `/api` | Creates REST/GraphQL APIs |
| `db-agent` | `/db` | Database operations, migrations |
| `test-agent` | `/test` | Writes and runs tests |
| `review-agent` | `/review` | Code review |
| `refactor-agent` | `/refactor` | Code refactoring |
| `debug-agent` | `/debug` | Debugging issues |
| `security-agent` | `/security` | Security audits |
| `docs-agent` | `/docs` | Documentation |
| `devops-agent` | `/devops` | CI/CD, Docker, deployment |
| `cache-agent` | (auto) | Caching decisions |
| `ai-agent` | (auto) | AI utilization points |
| `search-agent` | (auto) | Web search |
| `scrape-agent` | (auto) | Web scraping |

---

## Available Skills

| Skill | Purpose |
|-------|---------|
| `tdd` | Test-Driven Development workflow |
| `code-review` | Systematic code review |
| `git-workflow` | Git branching, commits, PRs |
| `changelog` | Generate changelogs |
| `architecture` | Software architecture patterns |
| `root-cause` | Root cause analysis |
| `web-scrape` | Extract content from websites |
| `web-search` | Search the web |
| `api-design` | RESTful API design |

---

## Hooks

| Event | Matcher | Behavior |
|-------|---------|----------|
| `PreToolUse` | `Bash` | **BLOCKS** git commit/push/reset/rebase/merge |
| `PreToolUse` | `Write\|Edit` | Warns when modifying sensitive files (.env, .pem, etc.) |
| `PostToolUse` | `Write\|Edit` | Logs file modifications |
| `PostToolUse` | `Bash` | Logs commands executed |
| `SubagentStop` | `*` | Logs agent completion |
| `SessionStart` | - | Logs session start |
| `Stop` | - | Logs session end + Ralph Wiggum check |

### Commit Protection

By default, these commands are **BLOCKED**:
- `git commit`
- `git push`
- `git rebase`
- `git merge`
- `git reset --hard`

Claude will ask for explicit confirmation before proceeding.

---

## Ralph Wiggum Plugin

The Ralph Wiggum pattern creates an iterative loop that keeps working until a completion promise is found.

### Starting a Loop

```bash
# Create state file
cat > .claude/ralph-state.json << 'EOF'
{
  "active": true,
  "iteration": 0,
  "max_iterations": 50,
  "completion_promise": "DONE",
  "prompt": "Build a REST API for todos with tests. Output <promise>DONE</promise> when complete."
}
EOF

# Run Claude
claude
```

### Canceling a Loop

```bash
echo '{"active": false}' > .claude/ralph-state.json
```

### Best Practices

1. **Clear completion criteria** - Define exactly what "done" means
2. **Set max_iterations** - Prevent runaway costs
3. **Use for automatable tasks** - Tests passing, batch operations
4. **Not for design decisions** - Needs human judgment

---

## Example Workflow

```
You: Add user authentication to the app

Claude: [planning-agent analyzes the request]

I'll implement user authentication. Here's my plan:
1. Create user model and database migration
2. Implement registration endpoint
3. Implement login endpoint with JWT
4. Add authentication middleware
5. Write tests

[Delegates to db-agent for migration]
[Delegates to api-agent for endpoints]
[Delegates to code-agent for middleware]
[Delegates to test-agent for tests]
[Uses tdd skill for test-first approach]

Done! All tests passing. Would you like me to commit these changes?

You: Yes, commit with message "feat: add user authentication"

Claude: [Commit protection hook prompts for confirmation]
Confirmed. Committing...
```

---

## Programmatic Usage

```python
from mcp_orchestrator import (
    setup_project,
    list_available_agents,
    list_available_skills,
    Agent,
    Skill,
    Hook,
)

# Set up a project
result = setup_project("/path/to/my-project")
print(f"Agents installed: {result['agents_copied']}")
print(f"Skills installed: {result['skills_copied']}")

# List available agents
for agent in list_available_agents():
    print(f"- {agent['name']}")

# Create custom agent
my_agent = Agent(
    name="my-custom-agent",
    description="Does something special",
    tools=["Read", "Write", "Bash"],
    priority=80
)
my_agent.save()  # Saves to .claude/agents/

# Create custom skill
my_skill = Skill(
    name="my-skill",
    description="A custom skill",
    tools=["Read", "Grep"],
    instructions="How to use this skill..."
)
my_skill.save()  # Saves to .claude/skills/
```

---

## Installation on Other Computers

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/mcp-orchestrator.git

# 2. Install package
cd mcp-orchestrator
pip install -e .

# 3. Set up any project
cd /path/to/any/project
python -c "from mcp_orchestrator import setup_project; setup_project('.')"

# 4. Use Claude Code
claude
```

That's it! The agents, skills, and hooks are now available in your project.

---

## Project Structure

```
mcp-orchestrator/
├── README.md
├── INSTALL.md
├── pyproject.toml           # Package configuration
├── mcp_orchestrator/        # Python SDK
│   ├── __init__.py
│   ├── setup.py             # setup_project() function
│   ├── agents.py
│   ├── skills.py
│   └── hooks.py
├── .claude/                  # Source definitions
│   ├── agents/              # 15 agents
│   ├── skills/              # 9 skills
│   ├── hooks/hooks.json     # Event hooks
│   ├── plugins/ralph-wiggum # Iteration plugin
│   └── settings.json
├── api/                     # Optional: Web server
└── core/                    # Optional: Pipeline logic
```

---

## Configuration

### Permissions (.claude/settings.json)

```json
{
  "permissions": {
    "allow_commit": false,
    "require_commit_confirmation": true
  },
  "agents": {
    "enabled": true,
    "auto_delegate": true
  },
  "hooks": {
    "enabled": true
  }
}
```

### Environment Variables

```bash
# Optional: For web search via Brave
export BRAVE_API_KEY=your_key

# Optional: Server port
export MCP_SERVER_PORT=8000
```

---

## FAQ

### Do I need an Anthropic API key?

**No.** This works with your Claude Code subscription. The agents, skills, and hooks are configuration files that Claude Code reads and uses.

### Will this auto-commit my code?

**No.** Git operations are blocked by default. Claude will always ask before committing.

### Can I customize the agents?

**Yes.** Edit the `.md` files in `.claude/agents/` or create new ones.

### Can I add my own skills?

**Yes.** Create a new folder in `.claude/skills/` with a `SKILL.md` file.

### How do I disable a hook?

Edit `.claude/hooks/hooks.json` and remove or modify the hook.

---

## License

MIT
