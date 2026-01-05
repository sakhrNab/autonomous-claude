"""
Chat UI

Chat-first UI implementation.

Per SESSION 2 Guide:
- Displays chat bubbles, voice/text messages
- Streaming replies
- Message-linked task updates
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import asyncio


class ChatBubbleType(Enum):
    """Types of chat bubbles."""
    USER_TEXT = "user_text"
    USER_VOICE = "user_voice"
    SYSTEM_TEXT = "system_text"
    SYSTEM_VOICE = "system_voice"
    TASK_UPDATE = "task_update"
    APPROVAL_REQUEST = "approval_request"
    ERROR = "error"
    INFO = "info"
    STREAMING = "streaming"


@dataclass
class ChatBubble:
    """A chat bubble for display."""
    bubble_id: str
    bubble_type: ChatBubbleType
    content: str
    timestamp: datetime
    user_id: str
    is_user: bool
    linked_tasks: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Streaming state
    is_streaming: bool = False
    stream_complete: bool = False

    # Voice
    audio_data: Optional[str] = None
    is_playing: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bubble_id": self.bubble_id,
            "bubble_type": self.bubble_type.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "is_user": self.is_user,
            "linked_tasks": self.linked_tasks,
            "metadata": self.metadata,
            "is_streaming": self.is_streaming,
            "has_audio": self.audio_data is not None,
        }


class ChatUI:
    """
    Chat UI - First-class chat interface.

    This UI handler:
    - Manages chat bubbles
    - Handles streaming responses
    - Links messages to tasks
    - Supports voice input/output
    - Provides real-time updates
    """

    def __init__(self):
        self.bubbles: Dict[str, ChatBubble] = {}
        self.sessions: Dict[str, List[str]] = {}  # session_id -> bubble_ids
        self.subscribers: Dict[str, List[Callable]] = {}
        self._bubble_counter = 0

    def _generate_bubble_id(self) -> str:
        """Generate a unique bubble ID."""
        self._bubble_counter += 1
        return f"bubble_{self._bubble_counter:06d}"

    def add_user_message(
        self,
        session_id: str,
        user_id: str,
        content: str,
        is_voice: bool = False,
        audio_data: Optional[str] = None,
        linked_tasks: Optional[List[str]] = None
    ) -> ChatBubble:
        """Add a user message bubble."""
        bubble_id = self._generate_bubble_id()

        bubble = ChatBubble(
            bubble_id=bubble_id,
            bubble_type=ChatBubbleType.USER_VOICE if is_voice else ChatBubbleType.USER_TEXT,
            content=content,
            timestamp=datetime.now(),
            user_id=user_id,
            is_user=True,
            linked_tasks=linked_tasks or [],
            audio_data=audio_data,
        )

        self._add_bubble(session_id, bubble)
        return bubble

    def add_system_message(
        self,
        session_id: str,
        content: str,
        bubble_type: ChatBubbleType = ChatBubbleType.SYSTEM_TEXT,
        linked_tasks: Optional[List[str]] = None,
        audio_data: Optional[str] = None
    ) -> ChatBubble:
        """Add a system message bubble."""
        bubble_id = self._generate_bubble_id()

        bubble = ChatBubble(
            bubble_id=bubble_id,
            bubble_type=bubble_type,
            content=content,
            timestamp=datetime.now(),
            user_id="system",
            is_user=False,
            linked_tasks=linked_tasks or [],
            audio_data=audio_data,
        )

        self._add_bubble(session_id, bubble)
        return bubble

    def start_streaming_response(
        self,
        session_id: str,
        initial_content: str = ""
    ) -> ChatBubble:
        """Start a streaming response bubble."""
        bubble_id = self._generate_bubble_id()

        bubble = ChatBubble(
            bubble_id=bubble_id,
            bubble_type=ChatBubbleType.STREAMING,
            content=initial_content,
            timestamp=datetime.now(),
            user_id="system",
            is_user=False,
            is_streaming=True,
        )

        self._add_bubble(session_id, bubble)
        return bubble

    def update_streaming_content(
        self,
        bubble_id: str,
        content: str,
        append: bool = True
    ):
        """Update content of a streaming bubble."""
        bubble = self.bubbles.get(bubble_id)
        if not bubble:
            return

        if append:
            bubble.content += content
        else:
            bubble.content = content

        self._notify_update(bubble)

    def complete_streaming(
        self,
        bubble_id: str,
        final_content: Optional[str] = None
    ):
        """Complete a streaming response."""
        bubble = self.bubbles.get(bubble_id)
        if not bubble:
            return

        if final_content:
            bubble.content = final_content

        bubble.is_streaming = False
        bubble.stream_complete = True
        bubble.bubble_type = ChatBubbleType.SYSTEM_TEXT

        self._notify_update(bubble)

    def add_task_update(
        self,
        session_id: str,
        task_id: str,
        status: str,
        description: str
    ) -> ChatBubble:
        """Add a task update bubble."""
        bubble_id = self._generate_bubble_id()

        content = f"Task Update: {description}\nStatus: {status}"

        bubble = ChatBubble(
            bubble_id=bubble_id,
            bubble_type=ChatBubbleType.TASK_UPDATE,
            content=content,
            timestamp=datetime.now(),
            user_id="system",
            is_user=False,
            linked_tasks=[task_id],
            metadata={"task_id": task_id, "status": status},
        )

        self._add_bubble(session_id, bubble)
        return bubble

    def add_approval_request(
        self,
        session_id: str,
        request_id: str,
        action: str,
        reason: str
    ) -> ChatBubble:
        """Add an approval request bubble."""
        bubble_id = self._generate_bubble_id()

        content = f"Approval Required\nAction: {action}\nReason: {reason}"

        bubble = ChatBubble(
            bubble_id=bubble_id,
            bubble_type=ChatBubbleType.APPROVAL_REQUEST,
            content=content,
            timestamp=datetime.now(),
            user_id="system",
            is_user=False,
            metadata={
                "request_id": request_id,
                "action": action,
                "awaiting_response": True,
            },
        )

        self._add_bubble(session_id, bubble)
        return bubble

    def add_error(
        self,
        session_id: str,
        error_message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> ChatBubble:
        """Add an error bubble."""
        bubble_id = self._generate_bubble_id()

        bubble = ChatBubble(
            bubble_id=bubble_id,
            bubble_type=ChatBubbleType.ERROR,
            content=error_message,
            timestamp=datetime.now(),
            user_id="system",
            is_user=False,
            metadata={"details": details or {}},
        )

        self._add_bubble(session_id, bubble)
        return bubble

    def link_task_to_bubble(self, bubble_id: str, task_id: str):
        """
        Link a task to a bubble.

        Per SESSION 2 Guide: Message-linked task updates.
        """
        bubble = self.bubbles.get(bubble_id)
        if bubble and task_id not in bubble.linked_tasks:
            bubble.linked_tasks.append(task_id)
            self._notify_update(bubble)

    def _add_bubble(self, session_id: str, bubble: ChatBubble):
        """Add a bubble to storage and notify subscribers."""
        self.bubbles[bubble.bubble_id] = bubble

        if session_id not in self.sessions:
            self.sessions[session_id] = []
        self.sessions[session_id].append(bubble.bubble_id)

        self._notify_new_bubble(session_id, bubble)

    def _notify_new_bubble(self, session_id: str, bubble: ChatBubble):
        """Notify subscribers of a new bubble."""
        for callback in self.subscribers.get(session_id, []):
            try:
                callback({
                    "event": "new_bubble",
                    "bubble": bubble.to_dict(),
                })
            except Exception:
                pass

    def _notify_update(self, bubble: ChatBubble):
        """Notify subscribers of a bubble update."""
        # Find session for this bubble
        session_id = None
        for sid, bubble_ids in self.sessions.items():
            if bubble.bubble_id in bubble_ids:
                session_id = sid
                break

        if session_id:
            for callback in self.subscribers.get(session_id, []):
                try:
                    callback({
                        "event": "update_bubble",
                        "bubble": bubble.to_dict(),
                    })
                except Exception:
                    pass

    def subscribe(self, session_id: str, callback: Callable):
        """Subscribe to chat updates for a session."""
        if session_id not in self.subscribers:
            self.subscribers[session_id] = []
        self.subscribers[session_id].append(callback)

    def unsubscribe(self, session_id: str, callback: Callable):
        """Unsubscribe from chat updates."""
        if session_id in self.subscribers:
            self.subscribers[session_id] = [
                cb for cb in self.subscribers[session_id]
                if cb != callback
            ]

    def get_session_bubbles(
        self,
        session_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get all bubbles for a session."""
        bubble_ids = self.sessions.get(session_id, [])
        bubbles = [
            self.bubbles[bid].to_dict()
            for bid in bubble_ids
            if bid in self.bubbles
        ]
        return bubbles[-limit:]

    def get_bubble(self, bubble_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific bubble."""
        bubble = self.bubbles.get(bubble_id)
        return bubble.to_dict() if bubble else None

    def clear_session(self, session_id: str):
        """Clear all bubbles for a session."""
        bubble_ids = self.sessions.pop(session_id, [])
        for bid in bubble_ids:
            self.bubbles.pop(bid, None)
