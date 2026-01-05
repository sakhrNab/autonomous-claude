"""
Timeline Handler

Manages the timeline view for the MCP orchestrator.

Per the guides, UI includes:
- Timeline of actions
- Live progress
- Approve / Reject buttons
- Retry / Pause / Stop
- Explain-why button
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class TimelineEventType(Enum):
    """Types of timeline events."""
    SESSION_START = "session_start"
    PLAN_CREATED = "plan_created"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    HOOK_DECISION = "hook_decision"
    SESSION_END = "session_end"
    ERROR = "error"
    INFO = "info"


@dataclass
class TimelineEvent:
    """A single event in the timeline."""
    event_id: str
    event_type: TimelineEventType
    timestamp: datetime
    title: str
    description: str
    details: Dict[str, Any] = field(default_factory=dict)
    session_id: Optional[str] = None
    agent_id: Optional[str] = None
    status: str = "completed"  # pending, in_progress, completed, failed


class TimelineHandler:
    """
    Timeline Handler - Manages execution timeline visualization.

    This handler:
    - Tracks all events in the execution
    - Provides real-time updates
    - Supports explanation generation
    - Enables user controls (pause, stop, retry)
    """

    def __init__(self):
        self.timelines: Dict[str, List[TimelineEvent]] = {}
        self.event_counter = 0
        self.subscribers: Dict[str, List[callable]] = {}

    def _generate_event_id(self) -> str:
        """Generate a unique event ID."""
        self.event_counter += 1
        return f"evt_{self.event_counter:06d}"

    def add_event(
        self,
        session_id: str,
        event_type: TimelineEventType,
        title: str,
        description: str,
        details: Optional[Dict[str, Any]] = None,
        agent_id: Optional[str] = None,
        status: str = "completed"
    ) -> TimelineEvent:
        """Add an event to the timeline."""
        if session_id not in self.timelines:
            self.timelines[session_id] = []

        event = TimelineEvent(
            event_id=self._generate_event_id(),
            event_type=event_type,
            timestamp=datetime.now(),
            title=title,
            description=description,
            details=details or {},
            session_id=session_id,
            agent_id=agent_id,
            status=status,
        )

        self.timelines[session_id].append(event)

        # Notify subscribers
        self._notify_subscribers(session_id, event)

        return event

    def get_timeline(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get the timeline for a session."""
        events = self.timelines.get(session_id, [])
        if limit:
            events = events[-limit:]

        return [
            {
                "event_id": e.event_id,
                "event_type": e.event_type.value,
                "timestamp": e.timestamp.isoformat(),
                "title": e.title,
                "description": e.description,
                "details": e.details,
                "agent_id": e.agent_id,
                "status": e.status,
            }
            for e in events
        ]

    def get_current_status(self, session_id: str) -> Dict[str, Any]:
        """Get the current status summary for a session."""
        events = self.timelines.get(session_id, [])

        if not events:
            return {"status": "unknown", "message": "No events"}

        last_event = events[-1]
        in_progress = [e for e in events if e.status == "in_progress"]

        return {
            "total_events": len(events),
            "last_event": {
                "type": last_event.event_type.value,
                "title": last_event.title,
                "timestamp": last_event.timestamp.isoformat(),
            },
            "in_progress_count": len(in_progress),
            "status": "running" if in_progress else "idle",
        }

    def explain_decision(self, session_id: str, event_id: str) -> Dict[str, Any]:
        """
        Generate an explanation for a decision.

        Per the guides, "Explain why" shows:
        - Planner reasoning
        - Hook decisions
        - Confidence levels
        """
        events = self.timelines.get(session_id, [])
        event = next((e for e in events if e.event_id == event_id), None)

        if not event:
            return {"error": "Event not found"}

        explanation = {
            "event_id": event_id,
            "event_type": event.event_type.value,
            "title": event.title,
            "description": event.description,
        }

        # Add type-specific explanations
        if event.event_type == TimelineEventType.HOOK_DECISION:
            explanation["reasoning"] = {
                "hook_type": event.details.get("hook_type"),
                "action": event.details.get("action"),
                "reason": event.details.get("reason"),
                "confidence": event.details.get("confidence"),
                "factors": event.details.get("factors", []),
            }
        elif event.event_type == TimelineEventType.PLAN_CREATED:
            explanation["reasoning"] = {
                "intent_analysis": event.details.get("intent_analysis"),
                "steps_count": len(event.details.get("steps", [])),
                "estimated_cost": event.details.get("estimated_cost"),
            }

        return explanation

    def subscribe(self, session_id: str, callback: callable):
        """Subscribe to timeline updates for a session."""
        if session_id not in self.subscribers:
            self.subscribers[session_id] = []
        self.subscribers[session_id].append(callback)

    def unsubscribe(self, session_id: str, callback: callable):
        """Unsubscribe from timeline updates."""
        if session_id in self.subscribers:
            self.subscribers[session_id] = [
                cb for cb in self.subscribers[session_id]
                if cb != callback
            ]

    def _notify_subscribers(self, session_id: str, event: TimelineEvent):
        """Notify subscribers of a new event."""
        for callback in self.subscribers.get(session_id, []):
            try:
                callback({
                    "event_id": event.event_id,
                    "event_type": event.event_type.value,
                    "title": event.title,
                    "timestamp": event.timestamp.isoformat(),
                })
            except Exception:
                pass  # Don't let subscriber errors break the flow

    # Convenience methods for common events

    def log_session_start(self, session_id: str, intent: str) -> TimelineEvent:
        """Log session start event."""
        return self.add_event(
            session_id,
            TimelineEventType.SESSION_START,
            "Session Started",
            f"Processing: {intent[:100]}...",
            {"intent": intent},
        )

    def log_plan_created(
        self,
        session_id: str,
        plan: Dict[str, Any]
    ) -> TimelineEvent:
        """Log plan creation event."""
        steps = plan.get("steps", plan.get("plan", []))
        return self.add_event(
            session_id,
            TimelineEventType.PLAN_CREATED,
            "Plan Created",
            f"Created plan with {len(steps)} steps",
            {"steps": steps, "step_count": len(steps)},
        )

    def log_task_started(
        self,
        session_id: str,
        task_name: str,
        agent_id: str
    ) -> TimelineEvent:
        """Log task start event."""
        return self.add_event(
            session_id,
            TimelineEventType.TASK_STARTED,
            f"Task: {task_name}",
            f"Started by {agent_id}",
            {"task_name": task_name},
            agent_id=agent_id,
            status="in_progress",
        )

    def log_task_completed(
        self,
        session_id: str,
        task_name: str,
        result: Dict[str, Any]
    ) -> TimelineEvent:
        """Log task completion event."""
        return self.add_event(
            session_id,
            TimelineEventType.TASK_COMPLETED,
            f"Completed: {task_name}",
            "Task completed successfully",
            {"result": result},
        )

    def log_task_failed(
        self,
        session_id: str,
        task_name: str,
        error: str
    ) -> TimelineEvent:
        """Log task failure event."""
        return self.add_event(
            session_id,
            TimelineEventType.TASK_FAILED,
            f"Failed: {task_name}",
            error,
            {"error": error},
            status="failed",
        )

    def log_approval_requested(
        self,
        session_id: str,
        action: str,
        reason: str
    ) -> TimelineEvent:
        """Log approval request event."""
        return self.add_event(
            session_id,
            TimelineEventType.APPROVAL_REQUESTED,
            "Approval Required",
            reason,
            {"action": action, "reason": reason},
            status="pending",
        )

    def log_hook_decision(
        self,
        session_id: str,
        hook_type: str,
        action: str,
        reason: str,
        confidence: float
    ) -> TimelineEvent:
        """Log hook decision event."""
        return self.add_event(
            session_id,
            TimelineEventType.HOOK_DECISION,
            f"Decision: {action}",
            reason,
            {
                "hook_type": hook_type,
                "action": action,
                "reason": reason,
                "confidence": confidence,
            },
        )

    def log_session_end(
        self,
        session_id: str,
        status: str,
        summary: Dict[str, Any]
    ) -> TimelineEvent:
        """Log session end event."""
        return self.add_event(
            session_id,
            TimelineEventType.SESSION_END,
            f"Session {status.title()}",
            f"Completed with status: {status}",
            {"status": status, "summary": summary},
        )
