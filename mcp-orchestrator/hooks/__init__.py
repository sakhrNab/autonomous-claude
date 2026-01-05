"""
MCP Hooks Module

Hooks run OUTSIDE the agent logic.
They control SAFETY and AUTONOMY.

The Stop Hook is the MOST IMPORTANT component.
It decides: continue, terminate, or escalate.
"""

from .base_hook import BaseHook, HookResult, HookAction
from .stop_hook import StopHook
from .pre_step_hook import PreStepHook
from .post_step_hook import PostStepHook
from .approval_hook import ApprovalHook

__all__ = [
    "BaseHook",
    "HookResult",
    "HookAction",
    "StopHook",
    "PreStepHook",
    "PostStepHook",
    "ApprovalHook",
]
