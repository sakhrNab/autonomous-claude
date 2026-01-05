"""
MCP Skills Module

Skills are ATOMIC capabilities.
They DO NOT plan.
They DO NOT loop.

Each skill:
- Takes arguments
- Does one thing
- Returns structured output

SESSION 2 additions:
- RouteMessage: Determines routing for messages to MCP/workflow/skill
"""

from .base_skill import BaseSkill, SkillResult
from .run_pipeline import RunPipeline
from .run_workflow import RunWorkflow
from .query_status import QueryStatus
from .fetch_logs import FetchLogs
from .apply_fix import ApplyFix
from .send_notification import SendNotification
from .speech_to_text import SpeechToText
from .text_to_speech import TextToSpeech

# Task skills
from .create_task_ledger import CreateTaskLedger
from .update_task_status import UpdateTaskStatus
from .append_task_notes import AppendTaskNotes
from .verify_task_completion import VerifyTaskCompletion
from .list_remaining_tasks import ListRemainingTasks

# Session 2 skills
from .route_message import RouteMessage

__all__ = [
    "BaseSkill",
    "SkillResult",
    # Core skills
    "RunPipeline",
    "RunWorkflow",
    "QueryStatus",
    "FetchLogs",
    "ApplyFix",
    "SendNotification",
    "SpeechToText",
    "TextToSpeech",
    # Task skills
    "CreateTaskLedger",
    "UpdateTaskStatus",
    "AppendTaskNotes",
    "VerifyTaskCompletion",
    "ListRemainingTasks",
    # Session 2 skills
    "RouteMessage",
]
