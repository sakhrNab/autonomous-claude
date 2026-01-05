"""
MCP State Module

Manages all state for the autonomous MCP orchestrator.

Memory types (per Part 2):
- Session Memory: Current execution state
- Operational Memory: Past failures/fixes
- User Preference Memory: Voice/text, thresholds
- Organizational Memory: Policies, SLAs

SESSION 2 additions:
- Message Store: First-class messages, threaded, linked to tasks
- Conversation Store: Conversation management
- Preference Learner: Memory with judgment (learns user preferences)
"""

from .session_store import SessionStore, Session
from .memory_store import MemoryStore, MemoryType
from .audit_logger import AuditLogger, AuditEvent
from .message_store import MessageStore, Message, MessageType, MessageStatus
from .conversation_store import ConversationStore, Conversation, ConversationState
from .preference_learner import PreferenceLearner, UserPreference, ApprovalPattern

__all__ = [
    "SessionStore",
    "Session",
    "MemoryStore",
    "MemoryType",
    "AuditLogger",
    "AuditEvent",
    # Session 2
    "MessageStore",
    "Message",
    "MessageType",
    "MessageStatus",
    "ConversationStore",
    "Conversation",
    "ConversationState",
    # Preference Learning
    "PreferenceLearner",
    "UserPreference",
    "ApprovalPattern",
]
