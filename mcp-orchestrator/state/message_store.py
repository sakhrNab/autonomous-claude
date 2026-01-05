"""
Message Store

Messages are FIRST-CLASS citizens in the system.
Every message:
- Has a unique ID
- Is timestamped
- Is linked to tasks
- Is threaded (can have parent/children)
- Persists for audit and continuity

Per SESSION 2 Guide:
- All messages generate linked tasks
- Stop Hook cannot terminate until linked tasks complete
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import uuid


class MessageType(Enum):
    """Types of messages."""
    USER_TEXT = "user_text"
    USER_VOICE = "user_voice"
    SYSTEM_RESPONSE = "system_response"
    SYSTEM_VOICE = "system_voice"
    AGENT_UPDATE = "agent_update"
    TASK_UPDATE = "task_update"
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_RESPONSE = "approval_response"
    ERROR = "error"
    INFO = "info"


class MessageStatus(Enum):
    """Status of a message."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Message:
    """
    A first-class message in the system.

    Fields per SESSION 2 Guide:
    - ID: Unique identifier
    - timestamp: When the message was created
    - user: User who sent/received
    - content: Message content
    - type: Message type
    - session: Session ID
    - linked_tasks: Tasks generated from this message
    """
    message_id: str
    timestamp: datetime
    user_id: str
    content: str
    message_type: MessageType
    session_id: str
    linked_tasks: List[str] = field(default_factory=list)

    # Threading
    parent_id: Optional[str] = None
    thread_id: Optional[str] = None

    # Status
    status: MessageStatus = MessageStatus.PENDING

    # Voice data
    audio_data: Optional[str] = None  # Base64 encoded
    transcript: Optional[str] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "content": self.content,
            "message_type": self.message_type.value,
            "session_id": self.session_id,
            "linked_tasks": self.linked_tasks,
            "parent_id": self.parent_id,
            "thread_id": self.thread_id,
            "status": self.status.value,
            "audio_data": self.audio_data,
            "transcript": self.transcript,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        return cls(
            message_id=data["message_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            user_id=data["user_id"],
            content=data["content"],
            message_type=MessageType(data["message_type"]),
            session_id=data["session_id"],
            linked_tasks=data.get("linked_tasks", []),
            parent_id=data.get("parent_id"),
            thread_id=data.get("thread_id"),
            status=MessageStatus(data.get("status", "pending")),
            audio_data=data.get("audio_data"),
            transcript=data.get("transcript"),
            metadata=data.get("metadata", {}),
        )


class MessageStore:
    """
    Message Store - Manages all messages.

    Messages are:
    - First-class citizens
    - Threaded
    - Always linked to tasks
    - Persisted for audit
    """

    def __init__(self, storage_path: str = "state/messages.json"):
        self.storage_path = Path(storage_path)
        self.messages: Dict[str, Message] = {}
        self.threads: Dict[str, List[str]] = {}  # thread_id -> message_ids
        self._load()

    def _load(self):
        """Load messages from storage."""
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                for msg_data in data.get("messages", []):
                    msg = Message.from_dict(msg_data)
                    self.messages[msg.message_id] = msg
                    if msg.thread_id:
                        if msg.thread_id not in self.threads:
                            self.threads[msg.thread_id] = []
                        self.threads[msg.thread_id].append(msg.message_id)
            except Exception:
                pass

    def _save(self):
        """Save messages to storage."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "updated_at": datetime.now().isoformat(),
            "message_count": len(self.messages),
            "messages": [m.to_dict() for m in self.messages.values()],
        }
        self.storage_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def create_message(
        self,
        user_id: str,
        content: str,
        message_type: MessageType,
        session_id: str,
        parent_id: Optional[str] = None,
        audio_data: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Message:
        """Create a new message."""
        message_id = str(uuid.uuid4())

        # Determine thread
        thread_id = None
        if parent_id and parent_id in self.messages:
            parent = self.messages[parent_id]
            thread_id = parent.thread_id or parent_id
        else:
            thread_id = message_id  # Start new thread

        message = Message(
            message_id=message_id,
            timestamp=datetime.now(),
            user_id=user_id,
            content=content,
            message_type=message_type,
            session_id=session_id,
            parent_id=parent_id,
            thread_id=thread_id,
            audio_data=audio_data,
            metadata=metadata or {},
        )

        self.messages[message_id] = message

        # Add to thread
        if thread_id not in self.threads:
            self.threads[thread_id] = []
        self.threads[thread_id].append(message_id)

        self._save()
        return message

    def get_message(self, message_id: str) -> Optional[Message]:
        """Get a message by ID."""
        return self.messages.get(message_id)

    def update_message(
        self,
        message_id: str,
        **updates
    ) -> Optional[Message]:
        """Update a message."""
        message = self.messages.get(message_id)
        if not message:
            return None

        for key, value in updates.items():
            if hasattr(message, key):
                setattr(message, key, value)

        self._save()
        return message

    def link_task(self, message_id: str, task_id: str) -> bool:
        """
        Link a task to a message.

        Per SESSION 2 Guide: All messages generate linked tasks.
        """
        message = self.messages.get(message_id)
        if not message:
            return False

        if task_id not in message.linked_tasks:
            message.linked_tasks.append(task_id)
            self._save()

        return True

    def get_linked_tasks(self, message_id: str) -> List[str]:
        """Get all tasks linked to a message."""
        message = self.messages.get(message_id)
        return message.linked_tasks if message else []

    def get_thread(self, thread_id: str) -> List[Message]:
        """Get all messages in a thread."""
        message_ids = self.threads.get(thread_id, [])
        return [
            self.messages[mid]
            for mid in message_ids
            if mid in self.messages
        ]

    def get_session_messages(
        self,
        session_id: str,
        limit: int = 100
    ) -> List[Message]:
        """Get all messages for a session."""
        messages = [
            m for m in self.messages.values()
            if m.session_id == session_id
        ]
        messages.sort(key=lambda m: m.timestamp)
        return messages[-limit:]

    def get_pending_messages(self) -> List[Message]:
        """Get all pending messages (not yet processed)."""
        return [
            m for m in self.messages.values()
            if m.status == MessageStatus.PENDING
        ]

    def get_messages_with_incomplete_tasks(self) -> List[Message]:
        """
        Get messages that have linked tasks that are not complete.

        Per SESSION 2 Guide: Stop Hook cannot terminate until
        all message-linked tasks are complete.
        """
        # This would check against the task ledger
        # For now, return messages with any linked tasks
        return [
            m for m in self.messages.values()
            if m.linked_tasks and m.status != MessageStatus.COMPLETED
        ]

    def mark_processing(self, message_id: str) -> bool:
        """Mark a message as processing."""
        return self.update_message(message_id, status=MessageStatus.PROCESSING) is not None

    def mark_completed(self, message_id: str) -> bool:
        """Mark a message as completed."""
        return self.update_message(message_id, status=MessageStatus.COMPLETED) is not None

    def mark_failed(self, message_id: str, error: str = "") -> bool:
        """Mark a message as failed."""
        message = self.messages.get(message_id)
        if message:
            message.status = MessageStatus.FAILED
            message.metadata["error"] = error
            self._save()
            return True
        return False
