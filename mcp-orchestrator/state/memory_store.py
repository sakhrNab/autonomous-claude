"""
Memory Store

Manages different types of memory for the MCP orchestrator.

Memory Types (per Part 2):
1) SESSION MEMORY - Current execution state
2) OPERATIONAL MEMORY - Past failures/fixes
3) USER PREFERENCE MEMORY - Voice/text, thresholds
4) ORGANIZATIONAL MEMORY - Policies, SLAs
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
import json


class MemoryType(Enum):
    """Types of memory in the system."""
    SESSION = "session"
    OPERATIONAL = "operational"
    USER_PREFERENCE = "user_preference"
    ORGANIZATIONAL = "organizational"


@dataclass
class MemoryEntry:
    """A single memory entry."""
    key: str
    value: Any
    memory_type: MemoryType
    created_at: datetime
    updated_at: datetime
    ttl_seconds: Optional[int] = None  # Time to live
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "memory_type": self.memory_type.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "ttl_seconds": self.ttl_seconds,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        return cls(
            key=data["key"],
            value=data["value"],
            memory_type=MemoryType(data["memory_type"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            ttl_seconds=data.get("ttl_seconds"),
            metadata=data.get("metadata", {}),
        )

    def is_expired(self) -> bool:
        """Check if this memory entry has expired."""
        if self.ttl_seconds is None:
            return False
        elapsed = (datetime.now() - self.created_at).total_seconds()
        return elapsed > self.ttl_seconds


class MemoryStore:
    """
    Memory Store - Manages all memory types.

    Read by:
    - Planner agent
    - Stop hook
    - Debugger agent

    Written by:
    - Post-step hook
    - Debugger agent
    - Approval outcomes
    """

    def __init__(self, storage_path: str = "state/memory.json"):
        self.storage_path = Path(storage_path)
        self.memory: Dict[str, MemoryEntry] = {}
        self._load()

    def _load(self):
        """Load memory from storage."""
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                for entry_data in data.get("entries", []):
                    entry = MemoryEntry.from_dict(entry_data)
                    if not entry.is_expired():
                        self.memory[entry.key] = entry
            except Exception:
                pass

    def _save(self):
        """Save memory to storage."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "updated_at": datetime.now().isoformat(),
            "entries": [e.to_dict() for e in self.memory.values() if not e.is_expired()],
        }
        self.storage_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def set(
        self,
        key: str,
        value: Any,
        memory_type: MemoryType,
        ttl_seconds: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MemoryEntry:
        """Set a memory entry."""
        now = datetime.now()

        entry = MemoryEntry(
            key=key,
            value=value,
            memory_type=memory_type,
            created_at=now,
            updated_at=now,
            ttl_seconds=ttl_seconds,
            metadata=metadata or {},
        )

        self.memory[key] = entry
        self._save()

        return entry

    def get(self, key: str) -> Optional[Any]:
        """Get a memory value by key."""
        entry = self.memory.get(key)
        if entry and not entry.is_expired():
            return entry.value
        return None

    def get_entry(self, key: str) -> Optional[MemoryEntry]:
        """Get the full memory entry."""
        entry = self.memory.get(key)
        if entry and not entry.is_expired():
            return entry
        return None

    def delete(self, key: str) -> bool:
        """Delete a memory entry."""
        if key in self.memory:
            del self.memory[key]
            self._save()
            return True
        return False

    def get_by_type(self, memory_type: MemoryType) -> Dict[str, Any]:
        """Get all memory entries of a specific type."""
        return {
            entry.key: entry.value
            for entry in self.memory.values()
            if entry.memory_type == memory_type and not entry.is_expired()
        }

    # Convenience methods for specific memory types

    def set_session_memory(self, key: str, value: Any, ttl_seconds: int = 3600):
        """Set session memory (expires after TTL)."""
        return self.set(key, value, MemoryType.SESSION, ttl_seconds=ttl_seconds)

    def set_operational_memory(self, key: str, value: Any):
        """Set operational memory (persists)."""
        return self.set(key, value, MemoryType.OPERATIONAL)

    def set_user_preference(self, user_id: str, preferences: Dict[str, Any]):
        """Set user preferences."""
        return self.set(f"user_prefs_{user_id}", preferences, MemoryType.USER_PREFERENCE)

    def get_user_preference(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user preferences."""
        return self.get(f"user_prefs_{user_id}")

    def set_org_policy(self, policy_name: str, policy: Dict[str, Any]):
        """Set organizational policy."""
        return self.set(f"org_policy_{policy_name}", policy, MemoryType.ORGANIZATIONAL)

    def get_org_policy(self, policy_name: str) -> Optional[Dict[str, Any]]:
        """Get organizational policy."""
        return self.get(f"org_policy_{policy_name}")

    # Failure/Fix memory for learning

    def record_failure(self, error_pattern: str, context: Dict[str, Any]):
        """Record a failure for learning."""
        key = f"failure_{error_pattern}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        return self.set(key, context, MemoryType.OPERATIONAL)

    def record_fix(self, error_pattern: str, fix: Dict[str, Any], success: bool):
        """Record a fix attempt for learning."""
        key = f"fix_{error_pattern}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        return self.set(
            key,
            {"fix": fix, "success": success, "timestamp": datetime.now().isoformat()},
            MemoryType.OPERATIONAL
        )

    def get_fix_history(self, error_pattern: str) -> List[Dict[str, Any]]:
        """Get history of fixes for an error pattern."""
        fixes = []
        for entry in self.memory.values():
            if (
                entry.memory_type == MemoryType.OPERATIONAL and
                entry.key.startswith(f"fix_{error_pattern}")
            ):
                fixes.append(entry.value)
        return fixes

    def cleanup_expired(self):
        """Remove expired entries."""
        expired_keys = [
            key for key, entry in self.memory.items()
            if entry.is_expired()
        ]
        for key in expired_keys:
            del self.memory[key]
        if expired_keys:
            self._save()
