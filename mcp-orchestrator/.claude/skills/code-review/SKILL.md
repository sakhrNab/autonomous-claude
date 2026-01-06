---
name: code-review
description: "Systematic code review following best practices"
allowed-tools: Read, Grep, Glob, LSP
---

# Code Review Skill

## Review Dimensions

### 1. Correctness
- Does it do what it's supposed to?
- Are edge cases handled?
- Are error cases handled?

### 2. Security
- Input validation?
- SQL injection?
- XSS vulnerabilities?
- Secrets in code?
- Authentication/authorization?

### 3. Performance
- Unnecessary loops?
- N+1 queries?
- Missing indexes?
- Memory leaks?

### 4. Maintainability
- Clear naming?
- Single responsibility?
- Appropriate abstractions?
- Code duplication?

### 5. Testing
- Are there tests?
- Good coverage?
- Edge cases tested?

## Review Output Format

```markdown
## Code Review: [file/feature]

### Summary
Brief overview of the changes.

### Issues Found

#### Critical
- [ ] Issue description (file:line)

#### High
- [ ] Issue description (file:line)

#### Medium
- [ ] Issue description (file:line)

#### Suggestions
- [ ] Improvement idea (file:line)

### What's Good
- Positive feedback

### Recommended Actions
1. Fix critical issues
2. Address high priority
3. Consider suggestions
```

## Quick Checklist

```
[ ] No secrets in code
[ ] Input is validated
[ ] Errors are handled
[ ] Tests exist and pass
[ ] No obvious security issues
[ ] Code is readable
[ ] No dead code
```
