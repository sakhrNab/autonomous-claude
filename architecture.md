# Autonomous MCP System Architecture

## Overview

This is an AUTONOMOUS, VOICE-FIRST MCP ORCHESTRATOR that:
- Converts voice/text into executable plans
- Spawns subagents to execute tasks
- Uses skills for atomic operations
- Enforces safety via hooks
- Runs continuously UNTIL THE TASK IS ACTUALLY DONE

## Core Loop

```
User Intent → Plan → Subagents → Skills → Cloud Code/Workflows
→ Stop Hook Decision → Continue OR Stop OR Escalate
```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    CLIENT (Web / Mobile)                     │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────────┐  │
│  │  Voice  │ │  Text    │ │ Timeline │ │  Approvals UI   │  │
│  │  Input  │ │ Fallback │ │   View   │ │                 │  │
│  └────┬────┘ └────┬─────┘ └────┬─────┘ └───────┬─────────┘  │
└───────┼───────────┼────────────┼───────────────┼────────────┘
        │           │            │               │
        └───────────┴─────┬──────┴───────────────┘
                          │ WebSocket / HTTP
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                        GATEWAY                               │
│   ┌──────┐  ┌──────────────┐  ┌─────────┐  ┌────────────┐   │
│   │ Auth │  │ Rate Limiting│  │ Session │  │ Streaming  │   │
│   └──────┘  └──────────────┘  └─────────┘  │   Events   │   │
│                                            └────────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              MCP ORCHESTRATOR (THE BRAIN)                    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                  Agent Manager                       │    │
│  │   Spawns, routes, and coordinates all subagents     │    │
│  └────────────────────────┬────────────────────────────┘    │
│                           │                                  │
│  ┌────────────────────────┴────────────────────────────┐    │
│  │                    SUBAGENTS                         │    │
│  │                                                      │    │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐     │    │
│  │  │  Planner   │  │  Executor  │  │  Monitor   │     │    │
│  │  │   Agent    │  │   Agent    │  │   Agent    │     │    │
│  │  └────────────┘  └────────────┘  └────────────┘     │    │
│  │                                                      │    │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐     │    │
│  │  │  Debugger  │  │  Approval  │  │   Task     │     │    │
│  │  │   Agent    │  │   Agent    │  │  Manager   │     │    │
│  │  └────────────┘  └────────────┘  └────────────┘     │    │
│  └─────────────────────────────────────────────────────┘    │
│                           │                                  │
│  ┌────────────────────────┴────────────────────────────┐    │
│  │                      HOOKS                           │    │
│  │  ┌──────────┐ ┌───────────┐ ┌───────────┐           │    │
│  │  │  Stop    │ │ Pre-step  │ │ Post-step │           │    │
│  │  │  Hook    │ │   Hook    │ │   Hook    │           │    │
│  │  └──────────┘ └───────────┘ └───────────┘           │    │
│  │  ┌──────────────────┐                               │    │
│  │  │  Approval Hook   │                               │    │
│  │  └──────────────────┘                               │    │
│  └─────────────────────────────────────────────────────┘    │
│                           │                                  │
│  ┌────────────────────────┴────────────────────────────┐    │
│  │                   STATE STORE                        │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐             │    │
│  │  │ Sessions │ │  Memory  │ │  Audit   │             │    │
│  │  │   .db    │ │   .db    │ │   .log   │             │    │
│  │  └──────────┘ └──────────┘ └──────────┘             │    │
│  └─────────────────────────────────────────────────────┘    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                        SKILLS                                │
│                                                              │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐ │
│  │  run_pipeline  │  │  run_workflow  │  │  query_status  │ │
│  └────────────────┘  └────────────────┘  └────────────────┘ │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐ │
│  │   fetch_logs   │  │   apply_fix    │  │ send_notif     │ │
│  └────────────────┘  └────────────────┘  └────────────────┘ │
│  ┌────────────────┐  ┌────────────────┐                     │
│  │ speech_to_text │  │ text_to_speech │                     │
│  └────────────────┘  └────────────────┘                     │
│                                                              │
│  TASK SKILLS:                                                │
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │create_task_ledger│  │update_task_status│                 │
│  └──────────────────┘  └──────────────────┘                 │
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │ append_task_notes│  │verify_completion │                 │
│  └──────────────────┘  └──────────────────┘                 │
│  ┌──────────────────┐                                       │
│  │list_remaining    │                                       │
│  └──────────────────┘                                       │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│             CLOUD CODE / WORKFLOWS (EXTERNAL)                │
│                                                              │
│  ┌───────────┐  ┌───────────┐  ┌───────────────────────┐    │
│  │    n8n    │  │ Pipelines │  │  External Services    │    │
│  └───────────┘  └───────────┘  └───────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

### Subagents

| Agent | Responsibility | Inputs | Outputs |
|-------|---------------|--------|---------|
| Planner | Create execution plans | User intent, context | Ordered step list |
| Executor | Run actions via skills | Plan steps | Execution results |
| Monitor | Observe long-running jobs | Job IDs | Status updates |
| Debugger | Analyze & fix failures | Error logs | Fixes applied |
| Approval | Human approval flow | Risky actions | Approval decision |
| Task Manager | Own the Task Ledger | Task updates | Validated transitions |

### Skills

| Skill | Purpose |
|-------|---------|
| run_pipeline | Trigger CI/CD pipeline |
| run_workflow | Trigger n8n/Temporal workflow |
| query_status | Get job status |
| fetch_logs | Retrieve logs/artifacts |
| apply_fix | Apply remediation |
| send_notification | Send Slack/email/voice |
| speech_to_text | Convert voice to text |
| text_to_speech | Convert text to voice |
| create_task_ledger | Initialize task ledger |
| update_task_status | Update task state |
| append_task_notes | Add notes to task |
| verify_task_completion | Validate completion |
| list_remaining_tasks | Show incomplete tasks |

### Hooks

| Hook | When | Purpose |
|------|------|---------|
| Stop Hook | After each iteration | Decide continue/terminate/escalate |
| Pre-step Hook | Before each step | Permission/budget checks |
| Post-step Hook | After skill execution | Test/validate results |
| Approval Hook | On risky actions | Block until human approves |

## Stop Hook Decision Tree

```
1) HARD STOPS (NO EXCEPTIONS)
   - iteration_count > MAX_ITERS → TERMINATE
   - elapsed_time > MAX_TIME → TERMINATE
   - budget_exceeded → TERMINATE
   - permission_violation → TERMINATE

2) TASK LEDGER CHECK
   - any task != Completed → CONTINUE

3) SUCCESS TESTS
   - all tests pass → TERMINATE (SUCCESS)

4) KNOWN FAILURE WITH REMEDIATION
   - error matches pattern + fix exists → CONTINUE

5) UNKNOWN / RISKY FAILURE
   - destructive/high-cost/unclear → ESCALATE

6) DEFAULT → CONTINUE
```

## Memory Types

| Type | Purpose | Read By | Written By |
|------|---------|---------|------------|
| Session | Current execution state | All agents | Post-step hook |
| Operational | Past failures/fixes | Planner, Debugger | Debugger |
| User Preference | Voice/text, thresholds | All agents | Approval outcomes |
| Organizational | Policies, SLAs | Stop hook | Admin |

## Security Controls

- RBAC per user and agent
- Capability-based skill permissions
- Budget caps per session
- Approval thresholds for risky actions
- Immutable audit logs
- Full action traceability

## Folder Structure

```
/mcp-orchestrator
├── /agents
│   ├── __init__.py
│   ├── agent_manager.py
│   ├── base_agent.py
│   ├── planner_agent.py
│   ├── executor_agent.py
│   ├── monitor_agent.py
│   ├── debugger_agent.py
│   ├── approval_agent.py
│   └── task_manager_agent.py
├── /skills
│   ├── __init__.py
│   ├── base_skill.py
│   ├── run_pipeline.py
│   ├── run_workflow.py
│   ├── query_status.py
│   ├── fetch_logs.py
│   ├── apply_fix.py
│   ├── send_notification.py
│   ├── speech_to_text.py
│   ├── text_to_speech.py
│   ├── create_task_ledger.py
│   ├── update_task_status.py
│   ├── append_task_notes.py
│   ├── verify_task_completion.py
│   └── list_remaining_tasks.py
├── /hooks
│   ├── __init__.py
│   ├── base_hook.py
│   ├── stop_hook.py
│   ├── pre_step_hook.py
│   ├── post_step_hook.py
│   └── approval_hook.py
├── /state
│   ├── __init__.py
│   ├── session_store.py
│   ├── memory_store.py
│   └── audit_logger.py
├── /ui
│   ├── __init__.py
│   ├── voice_handler.py
│   └── timeline_handler.py
├── /core
│   ├── __init__.py
│   ├── orchestrator.py
│   ├── workflow_engine.py
│   └── config.py
├── to-do.md
├── tasks.json
├── requirements.txt
└── README.md
```

## Non-Negotiable Rules

1. Every loop MUST have a stop hook
2. Every risky action MUST be approvable
3. Every decision MUST be logged
4. Every skill MUST be atomic
5. Every agent MUST have one role
6. Autonomy WITHOUT safety is FORBIDDEN
7. System CANNOT terminate until ALL tasks are complete
