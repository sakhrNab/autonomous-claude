---
name: git-workflow
description: "Git workflow management - branches, commits, PRs"
allowed-tools: Bash, Read, Write
---

# Git Workflow Skill

## Branch Naming

```
feature/   - New features
bugfix/    - Bug fixes
hotfix/    - Urgent production fixes
refactor/  - Code refactoring
docs/      - Documentation
test/      - Test additions
```

Examples:
- `feature/user-authentication`
- `bugfix/login-redirect`
- `hotfix/security-patch`

## Commit Messages

### Format
```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation
- `style` - Formatting
- `refactor` - Code restructuring
- `test` - Adding tests
- `chore` - Maintenance

### Examples
```
feat(auth): add JWT token refresh

Implemented automatic token refresh when token
expires within 5 minutes of a request.

Closes #123
```

## Workflow: Feature Development

```bash
# 1. Start from main
git checkout main
git pull origin main

# 2. Create feature branch
git checkout -b feature/my-feature

# 3. Make changes and commit
git add .
git commit -m "feat(scope): description"

# 4. Push and create PR
git push -u origin feature/my-feature
gh pr create --title "feat: my feature" --body "Description"

# 5. After approval, merge
gh pr merge --squash
```

## Workflow: Finishing a Branch

```bash
# 1. Ensure all tests pass
npm test  # or pytest, etc.

# 2. Rebase on main if needed
git fetch origin
git rebase origin/main

# 3. Squash if many commits
git rebase -i HEAD~N

# 4. Push and merge
git push --force-with-lease
gh pr merge
```

## Safety Rules

- NEVER force push to main/master
- NEVER commit secrets
- ALWAYS run tests before pushing
- ALWAYS create PR for review (unless solo project)
