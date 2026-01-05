"""
Audit Logger

Immutable audit logging for the MCP orchestrator.

Per the guides:
- EVERY ACTION MUST BE TRACEABLE
- voice -> transcript -> plan -> agent -> skill -> hook -> result

The audit log is IMMUTABLE and used for:
- Security auditing
- Debugging
- Compliance
- Learning
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
import json


class AuditEventType(Enum):
    """Types of audit events."""
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    INTENT_RECEIVED = "intent_received"
    PLAN_CREATED = "plan_created"
    AGENT_STEP = "agent_step"
    SKILL_EXECUTION = "skill_execution"
    HOOK_DECISION = "hook_decision"
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_RESPONSE = "approval_response"
    TASK_UPDATE = "task_update"
    ERROR = "error"
    SECURITY_EVENT = "security_event"


@dataclass
class AuditEvent:
    """A single audit event."""
    event_id: str
    event_type: AuditEventType
    timestamp: datetime
    session_id: str
    user_id: str
    agent_id: Optional[str]
    action: str
    details: Dict[str, Any]
    success: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "action": self.action,
            "details": self.details,
            "success": self.success,
            "error": self.error,
            "metadata": self.metadata,
        }

    def to_log_line(self) -> str:
        """Convert to a single log line."""
        return json.dumps(self.to_dict())


class AuditLogger:
    """
    Audit Logger - Immutable audit logging.

    Every action in the system is logged here.
    The log is append-only and cannot be modified.
    """

    def __init__(self, log_path: str = "state/audit.log"):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._event_counter = 0

    def _generate_event_id(self) -> str:
        """Generate a unique event ID."""
        self._event_counter += 1
        return f"evt_{datetime.now().strftime('%Y%m%d%H%M%S')}_{self._event_counter:06d}"

    def log(
        self,
        event_type: AuditEventType,
        session_id: str,
        user_id: str,
        action: str,
        details: Dict[str, Any],
        success: bool = True,
        agent_id: Optional[str] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AuditEvent:
        """
        Log an audit event.

        This is append-only - events cannot be modified.
        """
        event = AuditEvent(
            event_id=self._generate_event_id(),
            event_type=event_type,
            timestamp=datetime.now(),
            session_id=session_id,
            user_id=user_id,
            agent_id=agent_id,
            action=action,
            details=details,
            success=success,
            error=error,
            metadata=metadata or {},
        )

        # Append to log file
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(event.to_log_line() + "\n")

        return event

    # Convenience methods for common events

    def log_session_start(
        self,
        session_id: str,
        user_id: str,
        intent: str
    ) -> AuditEvent:
        """Log session start."""
        return self.log(
            AuditEventType.SESSION_START,
            session_id,
            user_id,
            "session_started",
            {"intent": intent},
        )

    def log_session_end(
        self,
        session_id: str,
        user_id: str,
        status: str,
        summary: Dict[str, Any]
    ) -> AuditEvent:
        """Log session end."""
        return self.log(
            AuditEventType.SESSION_END,
            session_id,
            user_id,
            "session_ended",
            {"status": status, "summary": summary},
        )

    def log_intent(
        self,
        session_id: str,
        user_id: str,
        intent: str,
        source: str = "text"
    ) -> AuditEvent:
        """Log user intent received."""
        return self.log(
            AuditEventType.INTENT_RECEIVED,
            session_id,
            user_id,
            "intent_received",
            {"intent": intent, "source": source},
        )

    def log_plan(
        self,
        session_id: str,
        user_id: str,
        plan: Dict[str, Any]
    ) -> AuditEvent:
        """Log plan creation."""
        return self.log(
            AuditEventType.PLAN_CREATED,
            session_id,
            user_id,
            "plan_created",
            {"plan": plan},
        )

    def log_agent_step(
        self,
        session_id: str,
        user_id: str,
        agent_id: str,
        iteration: int,
        action: str,
        result: Dict[str, Any],
        success: bool,
        error: Optional[str] = None
    ) -> AuditEvent:
        """Log agent step execution."""
        return self.log(
            AuditEventType.AGENT_STEP,
            session_id,
            user_id,
            action,
            {"iteration": iteration, "result": result},
            success=success,
            agent_id=agent_id,
            error=error,
        )

    def log_skill_execution(
        self,
        session_id: str,
        user_id: str,
        skill_name: str,
        args: Dict[str, Any],
        result: Dict[str, Any],
        success: bool,
        cost: float = 0.0,
        error: Optional[str] = None
    ) -> AuditEvent:
        """Log skill execution."""
        return self.log(
            AuditEventType.SKILL_EXECUTION,
            session_id,
            user_id,
            f"skill:{skill_name}",
            {"args": args, "result": result, "cost": cost},
            success=success,
            error=error,
        )

    def log_hook_decision(
        self,
        session_id: str,
        user_id: str,
        hook_name: str,
        action: str,
        reason: str,
        confidence: float
    ) -> AuditEvent:
        """Log hook decision."""
        return self.log(
            AuditEventType.HOOK_DECISION,
            session_id,
            user_id,
            f"hook:{hook_name}",
            {"action": action, "reason": reason, "confidence": confidence},
        )

    def log_approval_request(
        self,
        session_id: str,
        user_id: str,
        request_id: str,
        action: str,
        reason: str
    ) -> AuditEvent:
        """Log approval request."""
        return self.log(
            AuditEventType.APPROVAL_REQUEST,
            session_id,
            user_id,
            "approval_requested",
            {"request_id": request_id, "action": action, "reason": reason},
        )

    def log_approval_response(
        self,
        session_id: str,
        user_id: str,
        request_id: str,
        approved: bool,
        approver: str
    ) -> AuditEvent:
        """Log approval response."""
        return self.log(
            AuditEventType.APPROVAL_RESPONSE,
            session_id,
            user_id,
            "approval_responded",
            {"request_id": request_id, "approved": approved, "approver": approver},
        )

    def log_task_update(
        self,
        session_id: str,
        user_id: str,
        task_id: str,
        old_state: str,
        new_state: str,
        evidence: Optional[str] = None
    ) -> AuditEvent:
        """Log task state update."""
        return self.log(
            AuditEventType.TASK_UPDATE,
            session_id,
            user_id,
            "task_updated",
            {
                "task_id": task_id,
                "old_state": old_state,
                "new_state": new_state,
                "evidence": evidence,
            },
        )

    def log_error(
        self,
        session_id: str,
        user_id: str,
        error_type: str,
        error_message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> AuditEvent:
        """Log an error."""
        return self.log(
            AuditEventType.ERROR,
            session_id,
            user_id,
            f"error:{error_type}",
            details or {},
            success=False,
            error=error_message,
        )

    def log_security_event(
        self,
        session_id: str,
        user_id: str,
        event: str,
        details: Dict[str, Any]
    ) -> AuditEvent:
        """Log a security event."""
        return self.log(
            AuditEventType.SECURITY_EVENT,
            session_id,
            user_id,
            f"security:{event}",
            details,
        )

    def get_session_events(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all events for a session."""
        events = []
        if self.log_path.exists():
            with open(self.log_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        event = json.loads(line.strip())
                        if event.get("session_id") == session_id:
                            events.append(event)
                    except json.JSONDecodeError:
                        continue
        return events

    def get_recent_events(self, count: int = 100) -> List[Dict[str, Any]]:
        """Get the most recent events."""
        events = []
        if self.log_path.exists():
            with open(self.log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines[-count:]:
                    try:
                        events.append(json.loads(line.strip()))
                    except json.JSONDecodeError:
                        continue
        return events
