---
name: tdd
description: "Test-Driven Development - Write tests first, then implement"
allowed-tools: Read, Write, Edit, Bash, Grep
---

# Test-Driven Development (TDD)

## The TDD Cycle

```
RED → GREEN → REFACTOR → REPEAT
```

1. **RED** - Write a failing test
2. **GREEN** - Write minimum code to pass
3. **REFACTOR** - Improve code without breaking tests
4. **REPEAT** - Next test

## Process

### Step 1: Write Failing Test
```python
def test_user_can_login():
    user = create_user("test@example.com", "password123")
    result = login("test@example.com", "password123")
    assert result.success == True
    assert result.user.email == "test@example.com"
```

### Step 2: Run Test (Should Fail)
```bash
pytest tests/test_auth.py -v
```

### Step 3: Write Minimum Code
```python
def login(email, password):
    user = User.query.filter_by(email=email).first()
    if user and user.check_password(password):
        return LoginResult(success=True, user=user)
    return LoginResult(success=False)
```

### Step 4: Run Test (Should Pass)
```bash
pytest tests/test_auth.py -v
```

### Step 5: Refactor If Needed

### Step 6: Next Test

## Rules

- NEVER write implementation before test
- Each test should test ONE thing
- Tests should be independent
- Use descriptive test names
- Keep tests fast

## When to Use

- New features
- Bug fixes (write test that reproduces bug first)
- Refactoring (ensure tests exist first)

## Output

When using TDD, always show:
1. The test being written
2. The test failing
3. The implementation
4. The test passing
