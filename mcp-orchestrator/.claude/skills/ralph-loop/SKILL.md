---
name: ralph-loop
description: "Start an iterative loop that continues until task is complete"
allowed-tools: Bash, Read, Write, Edit, Grep, Glob
---

# Ralph Wiggum Loop

The Ralph Wiggum pattern creates a self-referential loop where Claude keeps working on a task until it outputs a completion promise.

## Usage

```
/ralph-loop "Your task description" --max-iterations 50 --completion-promise "DONE"
```

## How It Works

1. You provide a task with clear completion criteria
2. Claude works on the task
3. When Claude tries to stop, the Stop hook intercepts
4. If completion promise NOT found → Continue working
5. If completion promise found → Stop and report success
6. Safety limit prevents infinite loops

## Starting a Loop

To start a Ralph loop, create the state file:

```bash
cat > .claude/ralph-state.json << 'EOF'
{
  "active": true,
  "iteration": 0,
  "max_iterations": 50,
  "completion_promise": "DONE",
  "prompt": "Your task description here"
}
EOF
```

## Stopping a Loop

To cancel an active loop:

```bash
echo '{"active": false}' > .claude/ralph-state.json
```

Or use:
```
/cancel-ralph
```

## Writing Good Prompts

### Include Clear Completion Criteria

```
Build a REST API for user management.

Requirements:
- CRUD endpoints for users
- Input validation
- Error handling
- Unit tests with >80% coverage

When ALL requirements are met, output:
<promise>DONE</promise>
```

### Break Into Phases

```
Implement authentication system:

Phase 1: User registration (with tests)
Phase 2: Login/logout (with tests)
Phase 3: Password reset (with tests)
Phase 4: JWT tokens (with tests)

After each phase, verify tests pass.
When all phases complete, output: <promise>DONE</promise>
```

### Self-Correcting Loop

```
Fix all failing tests in the project.

Process:
1. Run tests
2. Identify failures
3. Fix one failure
4. Run tests again
5. Repeat until all pass

When ALL tests pass, output: <promise>DONE</promise>
```

## Cost Warning

Ralph loops can be expensive! Each iteration uses tokens.
- Set conservative max_iterations
- Monitor token usage
- Use for well-defined, automatable tasks

## Best For

- Getting tests to pass
- Implementing features with clear specs
- Refactoring with test coverage
- Batch operations

## Not Good For

- Tasks requiring design decisions
- Vague requirements
- Tasks needing human judgment
