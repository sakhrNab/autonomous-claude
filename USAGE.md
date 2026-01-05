# Autonomous MCP Orchestrator - Usage Guide

A trusted, conversation-driven autonomous operator that can take responsibility on your behalf.

## Quick Start

### 1. Install the Skill

The autonomous operator skill is in `.claude/skills/autonomous-operator/`. Claude Code will automatically detect it.

### 2. Configure Hooks

Hooks are already configured in `.claude/settings.json`. They handle:
- **Task ledger updates** after every action
- **Intelligent routing** of MCP calls
- **Completion checking** before stopping
- **Session initialization** with context
- **Intent analysis** for delegation detection

### 3. Start Using It

Just tell Claude what you want done:

```
"Handle the deployment for me"
"Take care of the API errors"
"Keep an eye on the database"
"Figure out why builds are failing"
```

The system will:
- Understand your intent
- Choose the right MCPs and workflows
- Execute autonomously
- Update the task ledger
- Report outcomes (not steps)

## How It Works

### The Five Principles

1. **Intent, not instructions** - Say what you want, not how to do it
2. **Trust with real stakes** - It handles real operations autonomously
3. **User forgets internals** - You think in outcomes, not agents/hooks/skills
4. **Memory with judgment** - It remembers your preferences and acts on them
5. **Silence as success** - No news is good news

### The Flow

```
User Intent
    ↓
Intent Analyzer Hook (detects delegation)
    ↓
Claude + Autonomous Operator Skill
    ↓
Decision Agent (selects MCP/workflow/skill)
    ↓
Execution (with intelligent routing)
    ↓
Task Ledger Update (after each action)
    ↓
Completion Checker (prevents premature stop)
    ↓
Outcome Report
```

## Key Components

### Claude Code Hooks (`.claude/hooks/`)

| Hook | File | Purpose |
|------|------|---------|
| PostToolUse | `task-ledger-update.py` | Updates task ledger after every action |
| PreToolUse (MCP) | `intelligent-router.py` | Routes MCPs based on risk and preferences |
| PreToolUse (Task) | `agent-selector.py` | Selects optimal subagent type |
| Stop | `completion-checker.py` | Prevents stopping until all tasks done |
| SessionStart | `session-init.py` | Loads context and preferences |
| UserPromptSubmit | `intent-analyzer.py` | Detects delegation intent |

### The Skill (`.claude/skills/autonomous-operator/SKILL.md`)

Teaches Claude how to:
- Operate with delegation authority
- Plan and execute autonomously
- Use the task ledger
- Escalate appropriately
- Report outcomes, not steps

### State Management (`mcp-orchestrator/state/`)

| Store | Purpose |
|-------|---------|
| `memory_store.py` | Session, operational, preference memory |
| `message_store.py` | First-class messages with task linking |
| `conversation_store.py` | Threaded conversations |
| `preference_learner.py` | Learns from your feedback |
| `session_store.py` | Session state |
| `audit_logger.py` | Audit trail |

### Agents (`mcp-orchestrator/agents/`)

- **PlannerAgent** - Creates execution plans
- **ExecutorAgent** - Runs plans
- **MonitorAgent** - Watches for issues
- **DebuggerAgent** - Fixes problems
- **ApprovalAgent** - Handles approvals
- **TaskManagerAgent** - Owns the task ledger
- **ConversationAgent** - Coordinates messages
- **DecisionAgent** - Dynamic routing

## Task Ledger

The task ledger (`to-do.md` or `to-do-session2.md`) is the **single source of truth**.

```markdown
[ ] pending task
[~] in progress
[x] completed (with evidence)
[!] blocked (with reason)
```

**CRITICAL**: The system cannot stop until ALL tasks are `[x]`.

## Preference Learning

The system learns from:
- **Approvals/Denials** - What you usually approve
- **Corrections** - When you tell it what was wrong
- **Feedback** - Implicit signals in your responses

It remembers:
- Risk tolerance (low/medium/high)
- Communication style (brief vs detailed)
- Autonomy preference (ask more vs just do it)
- What annoys you
- What you care about

## Escalation Rules

Will escalate ONLY when:
- Irreversible + high-risk action
- Budget threshold exceeded
- Needs human judgment
- Blocked after 3+ retries

Will NOT escalate for:
- Choosing between equivalent approaches
- Minor configuration
- Recoverable errors
- Read-only operations

## Customization

### User Preferences

Create `state/memory.json` with:

```json
{
  "entries": [
    {
      "key": "user_prefs_default",
      "value": {
        "risk_tolerance": "medium",
        "auto_approve_low_risk": true,
        "communication_style": "brief",
        "favorite_tools": ["github", "filesystem"]
      },
      "memory_type": "user_preference"
    }
  ]
}
```

### Organizational Policies

Create `state/policies.json`:

```json
{
  "require_approval_for": ["production_deploy", "data_deletion"],
  "auto_approve": ["staging_deploy", "log_access"],
  "blocked_actions": ["force_push_main"]
}
```

## File Structure

```
auotonomous-cloud/
├── .claude/
│   ├── settings.json          # Hook configuration
│   ├── hooks/                  # Hook scripts
│   │   ├── task-ledger-update.py
│   │   ├── intelligent-router.py
│   │   ├── completion-checker.py
│   │   ├── session-init.py
│   │   ├── intent-analyzer.py
│   │   └── agent-selector.py
│   └── skills/
│       └── autonomous-operator/
│           └── SKILL.md        # The skill definition
├── mcp-orchestrator/
│   ├── agents/                 # All agents
│   ├── skills/                 # All skills
│   ├── hooks/                  # Python hook implementations
│   ├── state/                  # State management
│   ├── core/                   # Core orchestrator
│   ├── ui/                     # Chat UI
│   └── tests/                  # Validation tests
├── state/                      # Runtime state (JSON/JSONL)
├── to-do.md                    # Task ledger (Session 1)
├── to-do-session2.md           # Task ledger (Session 2)
└── USAGE.md                    # This file
```

## Testing

Run the validation tests:

```bash
cd mcp-orchestrator/tests
python test_autonomous_flow.py
```

This validates:
- Hook configuration
- Skill definition
- State structure
- END GOAL criteria

## Common Patterns

### Delegation

```
User: "Handle the deployment"
System: [executes autonomously, updates task ledger]
System: "Deployed v2.3.4 to production. All checks passed."
```

### Monitoring

```
User: "Keep an eye on the API"
System: [sets up monitoring, defines thresholds]
System: "Monitoring active. Will alert on error rate >1% or latency >500ms."
```

### Debugging

```
User: "Fix the failing tests"
System: [investigates, identifies root cause, implements fix]
System: "Fixed: Missing mock in auth tests. All 47 tests now passing."
```

### Scheduled Tasks

```
User: "Run the backup every night"
System: [schedules via Scheduler]
System: "Scheduled: Daily backup at 2 AM UTC. Will retain 7 days."
```

## What Success Looks Like

You know it's working when:

1. You stop saying "run this, then that"
2. You start saying "handle this"
3. You trust it with real operations
4. You don't think about agents/hooks/skills
5. You're not interrupted unnecessarily
6. Things just get done

---

**Remember**: The end goal is not software. It's a trusted operator that handles things on your behalf.
