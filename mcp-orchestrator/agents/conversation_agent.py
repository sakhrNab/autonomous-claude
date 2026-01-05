"""
Conversation Agent

RESPONSIBILITY: Coordinate between user, orchestrator, and Cloud Code.

Per SESSION 2 Guide:
- Receives messages, stores them
- Routes to Planner Agent
- Updates task ledger CONTINUOUSLY
- All messages generate linked tasks
- Stop Hook cannot terminate until linked tasks complete
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent, AgentContext, AgentResult


@dataclass
class ConversationContext:
    """Context for conversation processing."""
    message_id: str
    user_id: str
    content: str
    message_type: str
    session_id: str
    conversation_id: Optional[str] = None
    parent_message_id: Optional[str] = None


class ConversationAgent(BaseAgent):
    """
    Conversation Agent - The conversation coordinator.

    This agent:
    - Receives all incoming messages (voice/text)
    - Stores messages with proper threading
    - Creates linked tasks for each message
    - Routes to Planner Agent for execution
    - Updates task ledger CONTINUOUSLY
    - Returns responses to the user
    """

    def __init__(self):
        super().__init__(name="ConversationAgent")
        self.message_store = None
        self.conversation_store = None
        self.task_manager = None
        self.planner = None

    def set_dependencies(
        self,
        message_store,
        conversation_store,
        task_manager,
        planner
    ):
        """Set dependencies for the conversation agent."""
        self.message_store = message_store
        self.conversation_store = conversation_store
        self.task_manager = task_manager
        self.planner = planner

    async def perform_step(self, context: AgentContext) -> AgentResult:
        """
        Process a conversation step.

        Per SESSION 2 Guide:
        - Receive message
        - Store message
        - Create linked task
        - Route to Planner
        - Update task ledger IMMEDIATELY
        """
        self.iteration_count += 1

        action = context.plan.get("action") if context.plan else "process_message"

        if action == "process_message":
            return await self._process_message(context)
        elif action == "get_history":
            return await self._get_history(context)
        elif action == "get_thread":
            return await self._get_thread(context)
        elif action == "respond":
            return await self._send_response(context)
        else:
            return AgentResult(
                success=False,
                error=f"Unknown action: {action}",
            )

    async def _process_message(self, context: AgentContext) -> AgentResult:
        """
        Process an incoming message.

        Flow:
        1) Store the message
        2) Create/get conversation
        3) Create linked task
        4) Route to Planner
        5) Update task ledger IMMEDIATELY
        """
        plan = context.plan or {}

        content = plan.get("content", "")
        message_type = plan.get("message_type", "user_text")
        parent_id = plan.get("parent_message_id")
        conversation_id = plan.get("conversation_id")

        self.log("info", "Processing message", {
            "content_preview": content[:100] if content else "",
            "type": message_type,
        })

        # Step 1: Store the message
        message_id = await self._store_message(
            user_id=context.user_id,
            content=content,
            message_type=message_type,
            session_id=context.session_id,
            parent_id=parent_id,
        )

        # Step 2: Get or create conversation
        if not conversation_id:
            conversation_id = await self._get_or_create_conversation(
                user_id=context.user_id,
                session_id=context.session_id,
            )

        # Add message to conversation
        await self._add_to_conversation(conversation_id, message_id)

        # Step 3: Create linked task for this message
        task_id = await self._create_linked_task(
            message_id=message_id,
            content=content,
            session_id=context.session_id,
        )

        # Step 4: Route to Planner for execution
        plan_result = await self._route_to_planner(
            content=content,
            message_id=message_id,
            task_id=task_id,
            context=context,
        )

        # Step 5: Update task ledger IMMEDIATELY
        await self._update_task_ledger(
            task_id=task_id,
            status="in_progress" if plan_result.get("success") else "blocked",
            evidence=f"Message processed, plan created: {plan_result.get('plan_id', 'N/A')}",
        )

        self.log("info", "Message processed", {
            "message_id": message_id,
            "task_id": task_id,
            "plan_success": plan_result.get("success"),
        })

        return AgentResult(
            success=True,
            data={
                "message_id": message_id,
                "conversation_id": conversation_id,
                "task_id": task_id,
                "plan": plan_result.get("plan"),
                "status": "processing",
            },
        )

    async def _store_message(
        self,
        user_id: str,
        content: str,
        message_type: str,
        session_id: str,
        parent_id: Optional[str] = None
    ) -> str:
        """Store a message and return its ID."""
        if self.message_store:
            from ..state.message_store import MessageType
            msg_type = MessageType(message_type) if message_type in [e.value for e in MessageType] else MessageType.USER_TEXT
            message = self.message_store.create_message(
                user_id=user_id,
                content=content,
                message_type=msg_type,
                session_id=session_id,
                parent_id=parent_id,
            )
            return message.message_id

        # Fallback if no message store
        import uuid
        return str(uuid.uuid4())

    async def _get_or_create_conversation(
        self,
        user_id: str,
        session_id: str
    ) -> str:
        """Get existing or create new conversation."""
        if self.conversation_store:
            conv = self.conversation_store.get_session_conversation(session_id)
            if conv:
                return conv.conversation_id

            new_conv = self.conversation_store.create_conversation(
                user_id=user_id,
                session_id=session_id,
            )
            return new_conv.conversation_id

        import uuid
        return str(uuid.uuid4())

    async def _add_to_conversation(self, conversation_id: str, message_id: str):
        """Add a message to a conversation."""
        if self.conversation_store:
            self.conversation_store.add_message(conversation_id, message_id)

    async def _create_linked_task(
        self,
        message_id: str,
        content: str,
        session_id: str
    ) -> str:
        """
        Create a task linked to this message.

        Per SESSION 2 Guide: All messages generate linked tasks.
        """
        task_id = f"msg_task_{message_id[:8]}"

        if self.task_manager:
            # Request task creation from Task Manager
            task_context = AgentContext(
                session_id=session_id,
                user_id="system",
                iteration=0,
                plan={
                    "action": "create_task",
                    "task_id": task_id,
                    "description": f"Process message: {content[:50]}...",
                    "linked_message": message_id,
                },
            )
            await self.task_manager.perform_step(task_context)

        # Link task to message
        if self.message_store:
            self.message_store.link_task(message_id, task_id)

        return task_id

    async def _route_to_planner(
        self,
        content: str,
        message_id: str,
        task_id: str,
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Route the message to Planner Agent for execution planning.

        Per SESSION 2 Guide: Every message triggers Planner → Agents → Skills → Cloud Code.
        """
        if self.planner:
            planner_context = AgentContext(
                session_id=context.session_id,
                user_id=context.user_id,
                iteration=context.iteration,
                plan={
                    "action": "create_plan",
                    "user_intent": content,
                    "source_message_id": message_id,
                    "linked_task_id": task_id,
                },
                permissions=context.permissions,
                budget_remaining=context.budget_remaining,
                time_started=context.time_started,
            )
            result = await self.planner.perform_step(planner_context)
            return {
                "success": result.success,
                "plan": result.data.get("plan") if result.data else None,
                "plan_id": result.data.get("plan_id") if result.data else None,
            }

        return {"success": False, "error": "No planner available"}

    async def _update_task_ledger(
        self,
        task_id: str,
        status: str,
        evidence: str
    ):
        """
        Update the task ledger IMMEDIATELY.

        Per SESSION 2 Guide: Task Ledger updates IMMEDIATELY after any action.
        """
        if self.task_manager:
            update_context = AgentContext(
                session_id="system",
                user_id="system",
                iteration=0,
                plan={
                    "action": "update_task",
                    "task_id": task_id,
                    "new_state": status,
                    "evidence": evidence if status == "completed" else None,
                    "reason": evidence if status == "blocked" else None,
                },
            )
            await self.task_manager.perform_step(update_context)

    async def _get_history(self, context: AgentContext) -> AgentResult:
        """Get conversation history."""
        session_id = context.plan.get("session_id") if context.plan else context.session_id
        limit = context.plan.get("limit", 50) if context.plan else 50

        messages = []
        if self.message_store:
            msgs = self.message_store.get_session_messages(session_id, limit)
            messages = [m.to_dict() for m in msgs]

        return AgentResult(
            success=True,
            data={"messages": messages, "count": len(messages)},
        )

    async def _get_thread(self, context: AgentContext) -> AgentResult:
        """Get a message thread."""
        thread_id = context.plan.get("thread_id") if context.plan else None

        if not thread_id:
            return AgentResult(
                success=False,
                error="thread_id required",
            )

        messages = []
        if self.message_store:
            msgs = self.message_store.get_thread(thread_id)
            messages = [m.to_dict() for m in msgs]

        return AgentResult(
            success=True,
            data={"thread_id": thread_id, "messages": messages},
        )

    async def _send_response(self, context: AgentContext) -> AgentResult:
        """Send a response message."""
        plan = context.plan or {}

        content = plan.get("content", "")
        parent_id = plan.get("parent_message_id")
        conversation_id = plan.get("conversation_id")

        # Store response message
        message_id = await self._store_message(
            user_id="system",
            content=content,
            message_type="system_response",
            session_id=context.session_id,
            parent_id=parent_id,
        )

        if conversation_id:
            await self._add_to_conversation(conversation_id, message_id)

        return AgentResult(
            success=True,
            data={
                "message_id": message_id,
                "content": content,
                "type": "response",
            },
        )
