"""
Session Store

Manages session state for the MCP orchestrator.
Sessions track the current execution state.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import uuid


class SessionState(Enum):
    """Possible session states."""
    CREATED = "created"
    PLANNING = "planning"
    EXECUTING = "executing"
    PAUSED = "paused"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    TERMINATED = "terminated"


@dataclass
class Session:
    """Represents an execution session."""
    session_id: str
    user_id: str
    state: SessionState
    created_at: datetime
    updated_at: datetime
    intent: str = ""
    plan: Optional[Dict[str, Any]] = None
    current_iteration: int = 0
    budget_spent: float = 0.0
    budget_limit: float = 100.0
    artifacts: List[str] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "intent": self.intent,
            "plan": self.plan,
            "current_iteration": self.current_iteration,
            "budget_spent": self.budget_spent,
            "budget_limit": self.budget_limit,
            "artifacts": self.artifacts,
            "logs": self.logs[-100:],  # Last 100 logs
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        return cls(
            session_id=data["session_id"],
            user_id=data["user_id"],
            state=SessionState(data["state"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            intent=data.get("intent", ""),
            plan=data.get("plan"),
            current_iteration=data.get("current_iteration", 0),
            budget_spent=data.get("budget_spent", 0.0),
            budget_limit=data.get("budget_limit", 100.0),
            artifacts=data.get("artifacts", []),
            logs=data.get("logs", []),
            metadata=data.get("metadata", {}),
        )


class SessionStore:
    """
    Session Store - Manages all session data.

    Sessions contain:
    - Current execution state
    - Intermediate artifacts
    - Temporary variables
    - Execution logs
    """

    def __init__(self, storage_path: str = "state/sessions.json"):
        self.storage_path = Path(storage_path)
        self.sessions: Dict[str, Session] = {}
        self._load()

    def _load(self):
        """Load sessions from storage."""
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                for session_data in data.get("sessions", []):
                    session = Session.from_dict(session_data)
                    self.sessions[session.session_id] = session
            except Exception:
                pass  # Start fresh if load fails

    def _save(self):
        """Save sessions to storage."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "updated_at": datetime.now().isoformat(),
            "sessions": [s.to_dict() for s in self.sessions.values()],
        }
        self.storage_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def create_session(
        self,
        user_id: str,
        intent: str = "",
        budget_limit: float = 100.0
    ) -> Session:
        """Create a new session."""
        session_id = str(uuid.uuid4())
        now = datetime.now()

        session = Session(
            session_id=session_id,
            user_id=user_id,
            state=SessionState.CREATED,
            created_at=now,
            updated_at=now,
            intent=intent,
            budget_limit=budget_limit,
        )

        self.sessions[session_id] = session
        self._save()

        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        return self.sessions.get(session_id)

    def update_session(
        self,
        session_id: str,
        **updates
    ) -> Optional[Session]:
        """Update session fields."""
        session = self.sessions.get(session_id)
        if not session:
            return None

        for key, value in updates.items():
            if hasattr(session, key):
                setattr(session, key, value)

        session.updated_at = datetime.now()
        self._save()

        return session

    def update_state(self, session_id: str, state: SessionState) -> Optional[Session]:
        """Update session state."""
        return self.update_session(session_id, state=state)

    def add_log(self, session_id: str, message: str) -> bool:
        """Add a log entry to a session."""
        session = self.sessions.get(session_id)
        if not session:
            return False

        timestamp = datetime.now().isoformat()
        session.logs.append(f"[{timestamp}] {message}")
        session.updated_at = datetime.now()
        self._save()

        return True

    def add_artifact(self, session_id: str, artifact_path: str) -> bool:
        """Add an artifact to a session."""
        session = self.sessions.get(session_id)
        if not session:
            return False

        session.artifacts.append(artifact_path)
        session.updated_at = datetime.now()
        self._save()

        return True

    def increment_iteration(self, session_id: str) -> int:
        """Increment the iteration counter."""
        session = self.sessions.get(session_id)
        if not session:
            return -1

        session.current_iteration += 1
        session.updated_at = datetime.now()
        self._save()

        return session.current_iteration

    def add_cost(self, session_id: str, cost: float) -> float:
        """Add cost to a session."""
        session = self.sessions.get(session_id)
        if not session:
            return -1

        session.budget_spent += cost
        session.updated_at = datetime.now()
        self._save()

        return session.budget_spent

    def get_active_sessions(self) -> List[Session]:
        """Get all active (non-completed) sessions."""
        return [
            s for s in self.sessions.values()
            if s.state not in [
                SessionState.COMPLETED,
                SessionState.FAILED,
                SessionState.TERMINATED,
            ]
        ]

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            self._save()
            return True
        return False
