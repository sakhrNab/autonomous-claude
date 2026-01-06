---
name: architecture
description: "Software architecture patterns and design principles"
allowed-tools: Read, Write, Glob, Grep
---

# Software Architecture Skill

## Core Principles

### SOLID
- **S**ingle Responsibility - One reason to change
- **O**pen/Closed - Open for extension, closed for modification
- **L**iskov Substitution - Subtypes must be substitutable
- **I**nterface Segregation - Small, specific interfaces
- **D**ependency Inversion - Depend on abstractions

### Clean Architecture Layers

```
┌─────────────────────────────────────┐
│           Presentation              │  ← UI, Controllers, CLI
├─────────────────────────────────────┤
│           Application               │  ← Use Cases, Services
├─────────────────────────────────────┤
│             Domain                  │  ← Entities, Business Logic
├─────────────────────────────────────┤
│          Infrastructure             │  ← DB, External APIs, File System
└─────────────────────────────────────┘
```

Dependencies point INWARD only.

## Common Patterns

### Repository Pattern
```python
class UserRepository(ABC):
    @abstractmethod
    def get_by_id(self, id: str) -> User: ...

    @abstractmethod
    def save(self, user: User) -> None: ...

class PostgresUserRepository(UserRepository):
    def get_by_id(self, id: str) -> User:
        # Database implementation
```

### Service Layer
```python
class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    def register(self, email: str, password: str) -> User:
        # Business logic here
        user = User(email=email)
        user.set_password(password)
        self.repo.save(user)
        return user
```

### Dependency Injection
```python
# Composition root
repo = PostgresUserRepository(db)
service = UserService(repo)
controller = UserController(service)
```

## Project Structure

```
src/
├── domain/           # Entities, value objects
│   └── user.py
├── application/      # Use cases, services
│   └── user_service.py
├── infrastructure/   # External concerns
│   ├── db/
│   └── api/
└── presentation/     # Controllers, CLI
    └── api/
```

## When to Apply

- New projects (design upfront)
- Growing codebases (gradual refactoring)
- Complex domains (need clear boundaries)
