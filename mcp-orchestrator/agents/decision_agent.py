"""
Decision Agent

RESPONSIBILITY: Dynamically choose the correct Agent/Skill/Hook to execute.

Per SESSION 2 Guide:
- Chooses correct Agent / Skill / Hook to execute a task or respond to a message
- Works dynamically
- Consults task ledger
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .base_agent import BaseAgent, AgentContext, AgentResult


@dataclass
class Decision:
    """A routing decision."""
    target_type: str  # "agent", "skill", "hook"
    target_name: str
    confidence: float
    reason: str
    args: Dict[str, Any]


class DecisionAgent(BaseAgent):
    """
    Decision Agent - Dynamic routing and decision making.

    This agent:
    - Analyzes incoming requests
    - Consults the task ledger
    - Determines the best agent/skill/hook to handle the request
    - Returns routing decisions with confidence scores
    """

    def __init__(self):
        super().__init__(name="DecisionAgent")

        # Define capabilities for routing
        self.agent_capabilities = {
            "planner": ["plan", "create_plan", "expand_task", "analyze_intent"],
            "executor": ["execute", "run", "trigger", "invoke"],
            "monitor": ["watch", "observe", "check_status", "poll"],
            "debugger": ["debug", "fix", "analyze_error", "troubleshoot"],
            "approval": ["approve", "reject", "escalate", "review"],
            "task_manager": ["create_task", "update_task", "verify_completion"],
            "conversation": ["message", "chat", "respond", "history"],
        }

        self.skill_capabilities = {
            "run_pipeline": ["pipeline", "ci", "cd", "deploy", "build"],
            "run_workflow": ["workflow", "n8n", "temporal", "automate"],
            "query_status": ["status", "check", "progress"],
            "fetch_logs": ["logs", "trace", "debug_info"],
            "apply_fix": ["fix", "repair", "patch", "remediate"],
            "send_notification": ["notify", "alert", "message", "slack", "email"],
            "speech_to_text": ["transcribe", "voice_input", "stt"],
            "text_to_speech": ["speak", "voice_output", "tts"],
            "route_message": ["route", "dispatch", "forward"],
        }

        self.hook_triggers = {
            "stop_hook": ["terminate", "complete", "finish", "end"],
            "pre_step_hook": ["before", "validate", "check_permission"],
            "post_step_hook": ["after", "verify", "test"],
            "approval_hook": ["approve", "costly", "destructive", "risky"],
        }

    async def perform_step(self, context: AgentContext) -> AgentResult:
        """
        Make a routing decision.

        Per SESSION 2 Guide: Consults task ledger and dynamically selects
        which agent/skill/hook to run.
        """
        self.iteration_count += 1

        action = context.plan.get("action") if context.plan else "decide"

        if action == "decide":
            return await self._make_decision(context)
        elif action == "suggest_next":
            return await self._suggest_next_action(context)
        elif action == "validate_route":
            return await self._validate_route(context)
        else:
            return AgentResult(
                success=False,
                error=f"Unknown action: {action}",
            )

    async def _make_decision(self, context: AgentContext) -> AgentResult:
        """
        Make a routing decision based on input.
        """
        plan = context.plan or {}

        intent = plan.get("intent", "")
        message_content = plan.get("content", "")
        task_context = plan.get("task_context", {})

        # Combine for analysis
        text = f"{intent} {message_content}".lower()

        # Get decisions for each type
        agent_decision = self._find_best_agent(text, task_context)
        skill_decision = self._find_best_skill(text, task_context)
        hook_decision = self._find_relevant_hook(text, task_context)

        # Choose the best overall decision
        decisions = []
        if agent_decision:
            decisions.append(agent_decision)
        if skill_decision:
            decisions.append(skill_decision)
        if hook_decision:
            decisions.append(hook_decision)

        if not decisions:
            # Default to planner for unknown intents
            decisions.append(Decision(
                target_type="agent",
                target_name="planner",
                confidence=0.5,
                reason="Default routing to planner for unknown intent",
                args={"intent": intent or message_content},
            ))

        # Sort by confidence
        decisions.sort(key=lambda d: d.confidence, reverse=True)
        best = decisions[0]

        self.log("info", "Decision made", {
            "target_type": best.target_type,
            "target_name": best.target_name,
            "confidence": best.confidence,
        })

        return AgentResult(
            success=True,
            data={
                "decision": {
                    "target_type": best.target_type,
                    "target_name": best.target_name,
                    "confidence": best.confidence,
                    "reason": best.reason,
                    "args": best.args,
                },
                "alternatives": [
                    {
                        "target_type": d.target_type,
                        "target_name": d.target_name,
                        "confidence": d.confidence,
                    }
                    for d in decisions[1:4]  # Top 3 alternatives
                ],
            },
        )

    def _find_best_agent(
        self,
        text: str,
        task_context: Dict[str, Any]
    ) -> Optional[Decision]:
        """Find the best agent for the request."""
        best_match = None
        best_score = 0.0

        for agent, keywords in self.agent_capabilities.items():
            score = sum(1 for kw in keywords if kw in text)
            normalized_score = score / len(keywords) if keywords else 0

            if normalized_score > best_score:
                best_score = normalized_score
                best_match = agent

        if best_match and best_score > 0:
            return Decision(
                target_type="agent",
                target_name=best_match,
                confidence=min(best_score + 0.3, 1.0),
                reason=f"Matched agent capabilities for {best_match}",
                args={"intent": text},
            )

        return None

    def _find_best_skill(
        self,
        text: str,
        task_context: Dict[str, Any]
    ) -> Optional[Decision]:
        """Find the best skill for the request."""
        best_match = None
        best_score = 0.0

        for skill, keywords in self.skill_capabilities.items():
            score = sum(1 for kw in keywords if kw in text)
            normalized_score = score / len(keywords) if keywords else 0

            if normalized_score > best_score:
                best_score = normalized_score
                best_match = skill

        if best_match and best_score > 0:
            return Decision(
                target_type="skill",
                target_name=best_match,
                confidence=min(best_score + 0.2, 1.0),
                reason=f"Matched skill capabilities for {best_match}",
                args={"skill_name": best_match},
            )

        return None

    def _find_relevant_hook(
        self,
        text: str,
        task_context: Dict[str, Any]
    ) -> Optional[Decision]:
        """Find if a hook should be triggered."""
        for hook, triggers in self.hook_triggers.items():
            if any(trigger in text for trigger in triggers):
                return Decision(
                    target_type="hook",
                    target_name=hook,
                    confidence=0.7,
                    reason=f"Hook trigger detected for {hook}",
                    args={"hook_name": hook},
                )

        return None

    async def _suggest_next_action(self, context: AgentContext) -> AgentResult:
        """
        Suggest the next action based on current state.

        Consults task ledger to determine what should happen next.
        """
        plan = context.plan or {}
        task_ledger = plan.get("task_ledger", {})
        current_state = plan.get("current_state", {})

        # Analyze task ledger
        pending_tasks = [
            t for t in task_ledger.get("tasks", [])
            if t.get("state") == "pending"
        ]
        in_progress_tasks = [
            t for t in task_ledger.get("tasks", [])
            if t.get("state") == "in_progress"
        ]
        blocked_tasks = [
            t for t in task_ledger.get("tasks", [])
            if t.get("state") == "blocked"
        ]

        # Determine next action
        if blocked_tasks:
            return AgentResult(
                success=True,
                data={
                    "suggestion": "escalate",
                    "reason": f"{len(blocked_tasks)} blocked tasks require attention",
                    "blocked_tasks": blocked_tasks,
                },
            )

        if in_progress_tasks:
            return AgentResult(
                success=True,
                data={
                    "suggestion": "continue",
                    "reason": "Tasks in progress, continue execution",
                    "in_progress": in_progress_tasks,
                },
            )

        if pending_tasks:
            next_task = pending_tasks[0]
            return AgentResult(
                success=True,
                data={
                    "suggestion": "execute",
                    "next_task": next_task,
                    "reason": f"Execute next pending task: {next_task.get('description', 'unknown')}",
                },
            )

        return AgentResult(
            success=True,
            data={
                "suggestion": "complete",
                "reason": "All tasks complete, ready for termination",
            },
        )

    async def _validate_route(self, context: AgentContext) -> AgentResult:
        """
        Validate a proposed routing decision.

        Checks if the route is valid given current permissions and state.
        """
        plan = context.plan or {}

        target_type = plan.get("target_type")
        target_name = plan.get("target_name")
        permissions = context.permissions

        # Validate target exists
        valid_targets = {
            "agent": list(self.agent_capabilities.keys()),
            "skill": list(self.skill_capabilities.keys()),
            "hook": list(self.hook_triggers.keys()),
        }

        if target_type not in valid_targets:
            return AgentResult(
                success=False,
                error=f"Invalid target type: {target_type}",
            )

        if target_name not in valid_targets[target_type]:
            return AgentResult(
                success=False,
                error=f"Unknown {target_type}: {target_name}",
            )

        # Check permissions (simplified)
        required_permission = f"{target_type}:{target_name}:execute"
        # In production, would check actual permissions

        return AgentResult(
            success=True,
            data={
                "valid": True,
                "target_type": target_type,
                "target_name": target_name,
            },
        )
