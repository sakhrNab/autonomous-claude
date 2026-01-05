"""
Conversation Store

Manages conversation state and history.
Conversations are threaded collections of messages.

Per SESSION 2 Guide:
- Messages are first-class, threaded, timestamped
- Must always link to tasks
- Conversation Agent coordinates between user and orchestrator
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import uuid


class ConversationState(Enum):
    """State of a conversation."""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


@dataclass
class Conversation:
    """
    A conversation - a collection of threaded messages.

    Each conversation:
    - Has a unique ID
    - Belongs to a user
    - Has a session
    - Contains messages
    - Tracks linked tasks
    """
    conversation_id: str
    user_id: str
    session_id: str
    title: str
    state: ConversationState
    created_at: datetime
    updated_at: datetime
    message_ids: List[str] = field(default_factory=list)
    linked_tasks: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "title": self.title,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "message_ids": self.message_ids,
            "linked_tasks": self.linked_tasks,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Conversation":
        return cls(
            conversation_id=data["conversation_id"],
            user_id=data["user_id"],
            session_id=data["session_id"],
            title=data.get("title", ""),
            state=ConversationState(data.get("state", "active")),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            message_ids=data.get("message_ids", []),
            linked_tasks=data.get("linked_tasks", []),
            metadata=data.get("metadata", {}),
        )


class ConversationStore:
    """
    Conversation Store - Manages conversations.

    Provides:
    - Conversation CRUD
    - Message tracking
    - Task linking
    - History retrieval
    """

    def __init__(self, storage_path: str = "state/conversations.json"):
        self.storage_path = Path(storage_path)
        self.conversations: Dict[str, Conversation] = {}
        self._load()

    def _load(self):
        """Load conversations from storage."""
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                for conv_data in data.get("conversations", []):
                    conv = Conversation.from_dict(conv_data)
                    self.conversations[conv.conversation_id] = conv
            except Exception:
                pass

    def _save(self):
        """Save conversations to storage."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "updated_at": datetime.now().isoformat(),
            "conversations": [c.to_dict() for c in self.conversations.values()],
        }
        self.storage_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def create_conversation(
        self,
        user_id: str,
        session_id: str,
        title: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Conversation:
        """Create a new conversation."""
        conversation_id = str(uuid.uuid4())
        now = datetime.now()

        conversation = Conversation(
            conversation_id=conversation_id,
            user_id=user_id,
            session_id=session_id,
            title=title or f"Conversation {now.strftime('%Y-%m-%d %H:%M')}",
            state=ConversationState.ACTIVE,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )

        self.conversations[conversation_id] = conversation
        self._save()

        return conversation

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by ID."""
        return self.conversations.get(conversation_id)

    def get_user_conversations(
        self,
        user_id: str,
        state: Optional[ConversationState] = None,
        limit: int = 50
    ) -> List[Conversation]:
        """Get conversations for a user."""
        conversations = [
            c for c in self.conversations.values()
            if c.user_id == user_id
        ]

        if state:
            conversations = [c for c in conversations if c.state == state]

        conversations.sort(key=lambda c: c.updated_at, reverse=True)
        return conversations[:limit]

    def get_session_conversation(self, session_id: str) -> Optional[Conversation]:
        """Get the conversation for a session."""
        for conv in self.conversations.values():
            if conv.session_id == session_id:
                return conv
        return None

    def add_message(self, conversation_id: str, message_id: str) -> bool:
        """Add a message to a conversation."""
        conversation = self.conversations.get(conversation_id)
        if not conversation:
            return False

        if message_id not in conversation.message_ids:
            conversation.message_ids.append(message_id)
            conversation.updated_at = datetime.now()
            self._save()

        return True

    def link_task(self, conversation_id: str, task_id: str) -> bool:
        """Link a task to a conversation."""
        conversation = self.conversations.get(conversation_id)
        if not conversation:
            return False

        if task_id not in conversation.linked_tasks:
            conversation.linked_tasks.append(task_id)
            conversation.updated_at = datetime.now()
            self._save()

        return True

    def update_state(
        self,
        conversation_id: str,
        state: ConversationState
    ) -> bool:
        """Update conversation state."""
        conversation = self.conversations.get(conversation_id)
        if not conversation:
            return False

        conversation.state = state
        conversation.updated_at = datetime.now()
        self._save()

        return True

    def update_title(self, conversation_id: str, title: str) -> bool:
        """Update conversation title."""
        conversation = self.conversations.get(conversation_id)
        if not conversation:
            return False

        conversation.title = title
        conversation.updated_at = datetime.now()
        self._save()

        return True

    def get_active_conversations(self) -> List[Conversation]:
        """Get all active conversations."""
        return [
            c for c in self.conversations.values()
            if c.state == ConversationState.ACTIVE
        ]

    def get_conversations_with_incomplete_tasks(self) -> List[Conversation]:
        """
        Get conversations that have linked tasks not yet complete.

        Per SESSION 2 Guide: Stop Hook checks these.
        """
        return [
            c for c in self.conversations.values()
            if c.linked_tasks and c.state == ConversationState.ACTIVE
        ]

    def archive_conversation(self, conversation_id: str) -> bool:
        """Archive a conversation."""
        return self.update_state(conversation_id, ConversationState.ARCHIVED)

    def complete_conversation(self, conversation_id: str) -> bool:
        """Mark a conversation as completed."""
        return self.update_state(conversation_id, ConversationState.COMPLETED)
