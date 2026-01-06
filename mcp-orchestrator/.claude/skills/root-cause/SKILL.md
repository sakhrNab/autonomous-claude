---
name: root-cause
description: "Root cause analysis for debugging and incident response"
allowed-tools: Read, Grep, Glob, Bash
---

# Root Cause Analysis Skill

## The 5 Whys Technique

Keep asking "Why?" until you reach the root cause.

**Example:**
1. Why did the server crash? → Out of memory
2. Why was it out of memory? → Too many connections
3. Why too many connections? → Connection pool not releasing
4. Why not releasing? → Missing `finally` block
5. Why missing? → No code review caught it

**Root Cause:** Missing code review process

## Debugging Flowchart

```
Error Reported
     │
     ▼
Can Reproduce?
  │      │
 Yes     No → Gather more info
  │
  ▼
Check Logs/Stack Trace
     │
     ▼
Identify Failing Component
     │
     ▼
Binary Search (git bisect if needed)
     │
     ▼
Found Root Cause
     │
     ▼
Fix + Add Test
     │
     ▼
Document (for future)
```

## Investigation Steps

### 1. Gather Information
```bash
# Recent changes
git log --oneline -20

# Error logs
grep -i "error\|exception" logs/app.log | tail -50

# System state
ps aux | head -20
df -h
free -m
```

### 2. Timeline
- When did it start?
- What changed around that time?
- Who was affected?

### 3. Reproduce
- Minimum steps to trigger
- Is it consistent or intermittent?
- Environment-specific?

### 4. Isolate
- Which component?
- Which function/line?
- Which input triggers it?

### 5. Fix
- Minimal change to fix
- Add test to prevent regression
- Document the fix

## Post-Mortem Template

```markdown
## Incident: [Title]

### Summary
One paragraph description.

### Timeline
- HH:MM - Event occurred
- HH:MM - Detected
- HH:MM - Resolved

### Root Cause
The actual underlying cause.

### Impact
Who/what was affected and for how long.

### Resolution
How it was fixed.

### Prevention
What will prevent this in the future.

### Action Items
- [ ] Specific action (owner)
```
