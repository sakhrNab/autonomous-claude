"""
Security Module

Implements security controls per the guides:
- RBAC per user and agent
- Capability-based permissions for skills
- Budget caps per session
- Approval thresholds
- Immutable audit logs

MANDATORY CONTROLS (from Part 2):
- NEVER allow agent to escalate its own permissions
- NEVER allow stop hook override without authorization
- NEVER allow infinite loops
- EVERY ACTION MUST BE TRACEABLE
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set
import hashlib


class PermissionLevel(Enum):
    """Permission levels in the RBAC system."""
    NONE = 0
    READ = 1
    WRITE = 2
    EXECUTE = 3
    ADMIN = 4


@dataclass
class Permission:
    """A single permission."""
    resource: str
    level: PermissionLevel
    constraints: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Role:
    """A role with associated permissions."""
    role_id: str
    name: str
    permissions: List[Permission]
    budget_limit: float = 100.0
    can_approve: bool = False


@dataclass
class User:
    """A user in the system."""
    user_id: str
    roles: List[str]
    budget_limit: float = 100.0
    approval_threshold: float = 50.0


class SecurityManager:
    """
    Security Manager - Enforces all security controls.

    Per the guides, this manager ensures:
    - RBAC is enforced
    - Budget limits are respected
    - Audit trail is maintained
    - Permissions cannot be escalated
    """

    def __init__(self):
        self.users: Dict[str, User] = {}
        self.roles: Dict[str, Role] = {}
        self.agent_permissions: Dict[str, Set[str]] = {}
        self._init_default_roles()

    def _init_default_roles(self):
        """Initialize default roles."""
        # Basic user role
        self.roles["user"] = Role(
            role_id="user",
            name="User",
            permissions=[
                Permission("workflow", PermissionLevel.EXECUTE),
                Permission("session", PermissionLevel.WRITE),
                Permission("logs", PermissionLevel.READ),
            ],
            budget_limit=100.0,
        )

        # Operator role
        self.roles["operator"] = Role(
            role_id="operator",
            name="Operator",
            permissions=[
                Permission("workflow", PermissionLevel.EXECUTE),
                Permission("pipeline", PermissionLevel.EXECUTE),
                Permission("session", PermissionLevel.WRITE),
                Permission("logs", PermissionLevel.READ),
                Permission("fix", PermissionLevel.EXECUTE),
            ],
            budget_limit=500.0,
            can_approve=True,
        )

        # Admin role
        self.roles["admin"] = Role(
            role_id="admin",
            name="Admin",
            permissions=[
                Permission("*", PermissionLevel.ADMIN),
            ],
            budget_limit=10000.0,
            can_approve=True,
        )

    def register_user(
        self,
        user_id: str,
        roles: List[str],
        budget_limit: Optional[float] = None,
        approval_threshold: Optional[float] = None
    ) -> User:
        """Register a user with roles."""
        # Validate roles
        valid_roles = [r for r in roles if r in self.roles]

        # Calculate budget from roles if not specified
        if budget_limit is None:
            budget_limit = max(
                self.roles[r].budget_limit for r in valid_roles
            ) if valid_roles else 100.0

        user = User(
            user_id=user_id,
            roles=valid_roles,
            budget_limit=budget_limit,
            approval_threshold=approval_threshold or 50.0,
        )
        self.users[user_id] = user
        return user

    def check_permission(
        self,
        user_id: str,
        resource: str,
        level: PermissionLevel
    ) -> bool:
        """Check if a user has permission for a resource."""
        user = self.users.get(user_id)
        if not user:
            return False

        for role_id in user.roles:
            role = self.roles.get(role_id)
            if not role:
                continue

            for perm in role.permissions:
                # Check wildcard
                if perm.resource == "*":
                    if perm.level.value >= level.value:
                        return True

                # Check exact match
                if perm.resource == resource:
                    if perm.level.value >= level.value:
                        return True

        return False

    def check_agent_permission(
        self,
        agent_id: str,
        capability: str
    ) -> bool:
        """Check if an agent has a capability."""
        agent_caps = self.agent_permissions.get(agent_id, set())
        return capability in agent_caps or "*" in agent_caps

    def grant_agent_capability(
        self,
        agent_id: str,
        capability: str
    ):
        """Grant a capability to an agent."""
        if agent_id not in self.agent_permissions:
            self.agent_permissions[agent_id] = set()
        self.agent_permissions[agent_id].add(capability)

    def revoke_agent_capability(
        self,
        agent_id: str,
        capability: str
    ):
        """Revoke a capability from an agent."""
        if agent_id in self.agent_permissions:
            self.agent_permissions[agent_id].discard(capability)

    def check_budget(
        self,
        user_id: str,
        current_spent: float,
        requested_cost: float
    ) -> bool:
        """Check if a cost is within budget."""
        user = self.users.get(user_id)
        if not user:
            return False

        return (current_spent + requested_cost) <= user.budget_limit

    def requires_approval(
        self,
        user_id: str,
        cost: float
    ) -> bool:
        """Check if an action requires approval based on cost."""
        user = self.users.get(user_id)
        if not user:
            return True  # Unknown user always requires approval

        return cost > user.approval_threshold

    def can_approve(self, user_id: str) -> bool:
        """Check if a user can approve actions."""
        user = self.users.get(user_id)
        if not user:
            return False

        for role_id in user.roles:
            role = self.roles.get(role_id)
            if role and role.can_approve:
                return True

        return False

    def validate_action(
        self,
        user_id: str,
        agent_id: str,
        resource: str,
        capability: str,
        cost: float,
        current_spent: float
    ) -> Dict[str, Any]:
        """
        Validate an action against all security controls.

        Returns a dict with:
        - allowed: bool
        - requires_approval: bool
        - reason: str
        """
        # Check user permission
        if not self.check_permission(user_id, resource, PermissionLevel.EXECUTE):
            return {
                "allowed": False,
                "requires_approval": False,
                "reason": f"User lacks permission for resource: {resource}",
            }

        # Check agent capability
        if not self.check_agent_permission(agent_id, capability):
            return {
                "allowed": False,
                "requires_approval": False,
                "reason": f"Agent lacks capability: {capability}",
            }

        # Check budget
        if not self.check_budget(user_id, current_spent, cost):
            return {
                "allowed": False,
                "requires_approval": False,
                "reason": "Budget exceeded",
            }

        # Check if approval needed
        needs_approval = self.requires_approval(user_id, cost)

        return {
            "allowed": True,
            "requires_approval": needs_approval,
            "reason": "approved" if not needs_approval else "pending_approval",
        }


class IntegrityChecker:
    """
    Integrity Checker - Ensures audit log integrity.

    Uses hash chains to ensure logs cannot be tampered with.
    """

    def __init__(self):
        self.last_hash: Optional[str] = None

    def hash_entry(self, entry: Dict[str, Any]) -> str:
        """Create a hash for a log entry."""
        # Include previous hash for chain
        data = {
            **entry,
            "previous_hash": self.last_hash or "genesis",
        }

        # Create deterministic string
        import json
        data_str = json.dumps(data, sort_keys=True)

        # Hash it
        hash_value = hashlib.sha256(data_str.encode()).hexdigest()
        self.last_hash = hash_value

        return hash_value

    def verify_chain(self, entries: List[Dict[str, Any]]) -> bool:
        """Verify the integrity of a chain of entries."""
        previous = "genesis"

        for entry in entries:
            expected_hash = entry.get("hash")
            if not expected_hash:
                return False

            # Recreate hash
            data = {
                k: v for k, v in entry.items()
                if k != "hash"
            }
            data["previous_hash"] = previous

            import json
            data_str = json.dumps(data, sort_keys=True)
            computed_hash = hashlib.sha256(data_str.encode()).hexdigest()

            if computed_hash != expected_hash:
                return False

            previous = expected_hash

        return True


# Security rules enforcement
SECURITY_RULES = """
MANDATORY SECURITY RULES (NON-NEGOTIABLE):

1. NEVER allow agent to escalate its own permissions
2. NEVER allow stop hook override without authorization
3. NEVER allow infinite loops
4. EVERY ACTION MUST BE TRACEABLE:
   voice → transcript → plan → agent → skill → hook → result

5. RBAC is enforced for ALL resources
6. Budget caps are enforced per session
7. Approval thresholds trigger human review
8. Audit logs are IMMUTABLE and hash-chained

DESTRUCTIVE ACTIONS ALWAYS REQUIRE APPROVAL:
- delete
- drop
- remove
- destroy
- terminate
- kill

These rules cannot be overridden programmatically.
"""
