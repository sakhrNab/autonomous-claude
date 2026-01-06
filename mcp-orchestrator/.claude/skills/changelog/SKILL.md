---
name: changelog
description: "Generate changelogs from git history"
allowed-tools: Bash, Read, Write
---

# Changelog Generation Skill

## Format (Keep a Changelog)

```markdown
# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [1.2.0] - 2024-01-15

### Added
- New feature X
- Support for Y

### Changed
- Updated Z behavior

### Fixed
- Bug in A
- Issue with B

### Removed
- Deprecated C

### Security
- Fixed vulnerability in D
```

## Generate from Git

```bash
# Get commits since last tag
git log $(git describe --tags --abbrev=0)..HEAD --pretty=format:"- %s" --reverse

# Group by type (if using conventional commits)
git log --pretty=format:"%s" | grep "^feat" | sed 's/^feat[:(]/Added: /'
git log --pretty=format:"%s" | grep "^fix" | sed 's/^fix[:(]/Fixed: /'
```

## Automation Script

```bash
#!/bin/bash
echo "## [Unreleased]"
echo ""
echo "### Added"
git log --pretty=format:"- %s" --grep="^feat" HEAD...$(git describe --tags --abbrev=0 2>/dev/null || echo HEAD~10)
echo ""
echo "### Fixed"
git log --pretty=format:"- %s" --grep="^fix" HEAD...$(git describe --tags --abbrev=0 2>/dev/null || echo HEAD~10)
```

## Customer-Friendly Version

Transform technical commits into user-friendly notes:

**Before:** `fix(auth): handle null user in session middleware`
**After:** `Fixed an issue where some users were unexpectedly logged out`

## Version Bumping

- **MAJOR** (1.0.0 → 2.0.0): Breaking changes
- **MINOR** (1.0.0 → 1.1.0): New features, backward compatible
- **PATCH** (1.0.0 → 1.0.1): Bug fixes, backward compatible
