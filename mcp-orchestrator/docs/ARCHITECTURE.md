# Autonomous Operator System Architecture

## Overview

The Autonomous Operator is a self-improving, self-healing system that can handle any task by intelligently routing it to the right combination of agents, skills, hooks, and MCPs.

## Core Principles

1. **Source of Truth First** - Every task consults the Source of Truth before execution
2. **Plan Before Execute** - Always create a plan, never execute blindly
3. **Test Everything** - No task is complete until tested
4. **Iterate Until Done** - Use Ralph Wiggum pattern for persistent iteration
5. **Learn and Adapt** - Create new capabilities when needed

## System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER REQUEST                              │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                     SOURCE OF TRUTH                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Capabilities│  │   Routing   │  │    Guidance Docs        │  │
│  │  Registry   │  │   Rules     │  │  (Architecture, Design) │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PLANNING AGENT                               │
│  - Analyzes task                                                 │
│  - Creates execution plan                                        │
│  - Updates TODO.md                                               │
│  - Determines hooks needed                                       │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
                    ▼             ▼             ▼
            ┌───────────┐  ┌───────────┐  ┌───────────┐
            │   HOOKS   │  │  AGENTS   │  │   MCPs    │
            │  BEFORE   │  │           │  │           │
            └───────────┘  └───────────┘  └───────────┘
                    │             │             │
                    └─────────────┼─────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                      EXECUTION ENGINE                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │    SKILLS   │  │   COMMANDS  │  │     API INTEGRATIONS    │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                       HOOKS AFTER                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  run-tests  │  │ update-todo │  │    check-completion     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
                        ┌─────────────────┐
                        │ <Promise>DONE   │
                        │ </Promise>      │
                        └─────────────────┘
```

## Data Flow

### 1. Task Reception
```
User Input → Source of Truth Lookup → Capability Matching
```

### 2. Planning Phase
```
Task → Planning Agent → Execution Plan → TODO.md Update
```

### 3. Pre-Execution Hooks
```
Plan → Check Design Patterns → Load Context → Check Cache → Check DB
```

### 4. Execution Phase
```
Plan → Primary Capability → Execute → Log Results
```

### 5. Post-Execution Hooks
```
Results → Run Tests → Update TODO → Check Completion
```

### 6. Completion Check
```
Results → Verify Tests Pass → Mark TODO Complete → <Promise>DONE</Promise>
```

## Agents

| Agent | Responsibility | Triggers |
|-------|---------------|----------|
| planning-agent | Task analysis, plan creation | plan, analyze, design |
| code-agent | Code writing and modification | implement, create, fix |
| testing-agent | Test creation and execution | test, verify, check |
| ui-design-agent | UI implementation | ui, page, component |
| database-agent | DB operations | database, sql, migration |

## Skills

| Skill | Responsibility | Dependencies |
|-------|---------------|--------------|
| web-search | Search the web | brave-search-mcp |
| web-scrape | Scrape websites | playwright-mcp |
| api-integration | External API calls | - |
| file-operations | File system ops | filesystem-mcp |

## Hooks

### Pre-Execution Hooks
- `load-context` - Load project context
- `check-design-patterns` - Verify patterns compliance
- `load-design-system` - Load UI design system
- `backup-db` - Create DB backup before migration
- `check-cache` - Check if data is cached
- `search-latest-version` - Search for latest library/MCP versions

### Post-Execution Hooks
- `run-tests` - Execute test suite
- `update-todo` - Update TODO.md status
- `check-completion` - Verify task completion
- `cache-response` - Cache API/DB responses

## MCPs (Model Context Protocol)

| MCP | Purpose |
|-----|---------|
| postgresql-mcp | Database operations |
| playwright-mcp | Browser automation |
| brave-search-mcp | Web search |
| filesystem-mcp | File operations |

## Iteration Pattern (Ralph Wiggum)

```python
max_iterations = 10
iteration = 0

while not task_complete and iteration < max_iterations:
    1. Execute task step
    2. Run tests
    3. If tests pass:
        - Mark step complete
        - Move to next step
    4. If tests fail:
        - Analyze failure
        - Adjust approach
        - iteration += 1

if task_complete:
    output("<Promise>DONE</Promise>")
else:
    output("<Promise>BLOCKED: {reason}</Promise>")
```

## File Structure

```
mcp-orchestrator/
├── core/
│   ├── source_of_truth.py      # Central brain
│   ├── planning_agent.py       # Task planning
│   ├── intelligent_orchestrator.py
│   └── self_healing.py
├── agents/
│   ├── code_agent.py
│   ├── testing_agent.py
│   ├── ui_design_agent.py
│   └── database_agent.py
├── skills/
│   ├── web_search.py
│   ├── web_scrape.py
│   ├── browser_automation.py
│   └── api_integration.py
├── hooks/
│   ├── update_todo.py
│   ├── run_tests.py
│   ├── check_design.py
│   └── search_latest.py
├── docs/
│   ├── ARCHITECTURE.md         # This file
│   ├── DESIGN_SYSTEM.md        # UI design patterns
│   └── PATTERNS.md             # Code patterns
├── source_of_truth/
│   ├── capabilities.json       # Capability registry
│   ├── routing_rules.json      # Routing rules
│   └── guidance.json           # Guidance documents
└── TODO.md                     # Active task list
```

## Completion Promise Format

```markdown
## Task: [Task Name]

### Status: [IN_PROGRESS | TESTING | BLOCKED | DONE]

### Steps:
1. [x] Step 1 - Description
2. [x] Step 2 - Description
3. [ ] Step 3 - Description

### Test Results:
- [x] Test 1 passed
- [ ] Test 2 pending

### Completion:
<Promise>DONE</Promise>
<!-- or -->
<Promise>BLOCKED: [Reason]</Promise>
```

## Integration as Library

To use this system in another project:

```python
from mcp_orchestrator import AutonomousOperator

operator = AutonomousOperator(project_path="/path/to/project")
result = operator.execute("Build a REST API for user management")

# The system will:
# 1. Consult Source of Truth
# 2. Create a plan
# 3. Execute with appropriate agents/skills
# 4. Test
# 5. Return result with <Promise>DONE</Promise>
```

## Web Search Policy

The system ALWAYS searches the web when:
1. Installing new libraries - to get latest versions
2. Using new MCPs - to get latest documentation
3. Task involves current events or latest info
4. User explicitly asks for latest/current information
5. Implementing new patterns - to find best practices

## Caching Policy

Cache is checked/updated when:
1. Making API calls - cache responses
2. Database queries - cache frequent queries
3. Web searches - cache recent results
4. File operations - cache file contents

## Error Handling

```
Error → Log Error → Analyze Cause →
  → If recoverable: Retry with adjustment
  → If not recoverable: <Promise>BLOCKED: {reason}</Promise>
```

Maximum retries: 10 iterations
After max retries: Report what was attempted and suggest alternatives
