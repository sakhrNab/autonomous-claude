"""
Chat-Workflow-Chat Loop Validation Tests

Per SESSION 2 Guide:
- Message → Planner → Agents → Skills → Cloud Code → results → reply
- End-to-end test working

This module validates the complete flow:
1. User sends message
2. Conversation Agent receives and stores message
3. Conversation Agent creates linked task
4. Planner Agent creates execution plan
5. Executor Agent runs plan with skills
6. Cloud Code adapter triggers remote execution
7. Results returned and response sent
8. Task ledger updated throughout
"""

import asyncio
from datetime import datetime
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock


async def test_chat_workflow_chat_loop():
    """
    Test the complete chat → workflow → chat loop.

    This validates SESSION 2 requirement:
    "Message → Planner → Agents → Skills → Cloud Code → results → reply"
    """
    from ..state.message_store import MessageStore, MessageType
    from ..state.conversation_store import ConversationStore
    from ..agents.conversation_agent import ConversationAgent
    from ..agents.planner_agent import PlannerAgent
    from ..agents.task_manager_agent import TaskManagerAgent
    from ..agents.base_agent import AgentContext
    from ..core.cloud_code_adapter import CloudCodeAdapter, CloudCodeProvider

    # Setup stores
    message_store = MessageStore(storage_path="state/test_messages.json")
    conversation_store = ConversationStore(storage_path="state/test_conversations.json")

    # Setup agents
    task_manager = TaskManagerAgent(
        ledger_path="test_to-do.md",
        tasks_json_path="test_tasks.json"
    )
    planner = PlannerAgent()
    conversation_agent = ConversationAgent()

    # Configure dependencies
    conversation_agent.set_dependencies(
        message_store=message_store,
        conversation_store=conversation_store,
        task_manager=task_manager,
        planner=planner,
    )

    # Setup Cloud Code adapter (mocked)
    cloud_adapter = CloudCodeAdapter(provider=CloudCodeProvider.MOCK)

    # Step 1: User sends message
    test_message = "Run the daily deployment workflow"
    user_id = "test_user"
    session_id = "test_session_001"

    context = AgentContext(
        session_id=session_id,
        user_id=user_id,
        iteration=0,
        plan={
            "action": "process_message",
            "content": test_message,
            "message_type": "user_text",
        },
        permissions={"workflow": True, "mcp": True},
        budget_remaining=100.0,
        time_started=datetime.now(),
    )

    # Step 2: Conversation Agent processes message
    result = await conversation_agent.perform_step(context)

    # Validate results
    assert result.success, f"Message processing failed: {result.error}"
    assert "message_id" in result.data, "No message_id returned"
    assert "task_id" in result.data, "No linked task_id returned"
    assert "conversation_id" in result.data, "No conversation_id returned"

    message_id = result.data["message_id"]
    task_id = result.data["task_id"]

    # Step 3: Verify message was stored with linked task
    stored_message = message_store.get_message(message_id)
    assert stored_message is not None, "Message not stored"
    assert task_id in stored_message.linked_tasks, "Task not linked to message"

    # Step 4: Verify conversation was created
    conversation_id = result.data["conversation_id"]
    conversation = conversation_store.get_conversation(conversation_id)
    assert conversation is not None, "Conversation not created"
    assert message_id in conversation.message_ids, "Message not in conversation"

    # Step 5: Simulate workflow execution via Cloud Code
    workflow_result = await cloud_adapter.trigger_workflow(
        workflow_name="daily-deployment",
        input_data={"source": "test"},
        message_id=message_id,
        task_id=task_id,
        session_id=session_id,
    )

    assert workflow_result.success, "Workflow execution failed"

    # Step 6: Send response
    response_context = AgentContext(
        session_id=session_id,
        user_id="system",
        iteration=1,
        plan={
            "action": "respond",
            "content": f"Workflow completed: {workflow_result.data.get('status', 'done')}",
            "parent_message_id": message_id,
            "conversation_id": conversation_id,
        },
        permissions=context.permissions,
        budget_remaining=context.budget_remaining,
        time_started=context.time_started,
    )

    response_result = await conversation_agent.perform_step(response_context)
    assert response_result.success, "Response failed"

    print("✓ Chat → Workflow → Chat loop validation PASSED")
    return {
        "success": True,
        "message_id": message_id,
        "task_id": task_id,
        "conversation_id": conversation_id,
        "workflow_result": workflow_result.data,
    }


async def test_message_linked_task_creation():
    """
    Test that all messages generate linked tasks.

    Per SESSION 2 Guide: "All messages generate linked tasks"
    """
    from ..state.message_store import MessageStore, MessageType
    from ..agents.conversation_agent import ConversationAgent
    from ..agents.task_manager_agent import TaskManagerAgent
    from ..agents.base_agent import AgentContext

    message_store = MessageStore(storage_path="state/test_msg_link.json")
    task_manager = TaskManagerAgent(
        ledger_path="test_link_todo.md",
        tasks_json_path="test_link_tasks.json"
    )

    conversation_agent = ConversationAgent()
    conversation_agent.set_dependencies(
        message_store=message_store,
        conversation_store=None,
        task_manager=task_manager,
        planner=None,
    )

    # Process multiple messages
    messages_to_test = [
        "Deploy the application",
        "Check the logs",
        "Restart the service",
    ]

    linked_tasks = []

    for msg_content in messages_to_test:
        context = AgentContext(
            session_id="test_session",
            user_id="test_user",
            iteration=0,
            plan={
                "action": "process_message",
                "content": msg_content,
                "message_type": "user_text",
            },
        )

        result = await conversation_agent.perform_step(context)

        if result.success and result.data:
            message_id = result.data.get("message_id")
            task_id = result.data.get("task_id")

            if message_id and task_id:
                message = message_store.get_message(message_id)
                assert task_id in message.linked_tasks, f"Task {task_id} not linked to message"
                linked_tasks.append(task_id)

    assert len(linked_tasks) == len(messages_to_test), "Not all messages got linked tasks"
    print(f"✓ Message-linked task creation PASSED ({len(linked_tasks)} tasks created)")

    return {"success": True, "linked_tasks": linked_tasks}


async def test_continuous_task_ledger_updates():
    """
    Test that task ledger is updated continuously.

    Per SESSION 2 Guide: "Task Ledger updates IMMEDIATELY after any action"
    """
    from ..agents.task_manager_agent import TaskManagerAgent, TaskState
    from ..agents.base_agent import AgentContext

    task_manager = TaskManagerAgent(
        ledger_path="test_continuous_todo.md",
        tasks_json_path="test_continuous_tasks.json"
    )

    # Create initial tasks
    create_context = AgentContext(
        session_id="test_session",
        user_id="system",
        iteration=0,
        plan={
            "action": "create_ledger",
            "tasks": [
                "Task 1: Initial task",
                "Task 2: Second task",
                "Task 3: Third task",
            ],
        },
    )

    await task_manager.perform_step(create_context)

    # Verify tasks created
    status_result = await task_manager.perform_step(AgentContext(
        session_id="test_session",
        user_id="system",
        iteration=1,
        plan={"action": "get_status"},
    ))

    assert status_result.data["total"] == 3, "Tasks not created"
    assert status_result.data["pending"] == 3, "Tasks should be pending"

    # Update first task to in_progress
    await task_manager.perform_step(AgentContext(
        session_id="test_session",
        user_id="system",
        iteration=2,
        plan={
            "action": "update_task",
            "task_id": "task_1",
            "new_state": "in_progress",
        },
    ))

    # Verify update was immediate
    status_result = await task_manager.perform_step(AgentContext(
        session_id="test_session",
        user_id="system",
        iteration=3,
        plan={"action": "get_status"},
    ))

    assert status_result.data["in_progress"] == 1, "Task not updated to in_progress"

    # Complete the task with evidence
    await task_manager.perform_step(AgentContext(
        session_id="test_session",
        user_id="system",
        iteration=4,
        plan={
            "action": "update_task",
            "task_id": "task_1",
            "new_state": "completed",
            "evidence": "Task completed successfully - verified via test",
        },
    ))

    # Verify completion
    status_result = await task_manager.perform_step(AgentContext(
        session_id="test_session",
        user_id="system",
        iteration=5,
        plan={"action": "get_status"},
    ))

    assert status_result.data["completed"] == 1, "Task not marked completed"

    print("✓ Continuous task ledger updates PASSED")
    return {"success": True, "final_status": status_result.data}


async def run_all_validations():
    """Run all Session 2 validation tests."""
    results = {}

    print("\n" + "="*60)
    print("SESSION 2 VALIDATION TESTS")
    print("="*60 + "\n")

    try:
        results["chat_workflow_loop"] = await test_chat_workflow_chat_loop()
    except Exception as e:
        results["chat_workflow_loop"] = {"success": False, "error": str(e)}
        print(f"✗ Chat-Workflow-Chat loop FAILED: {e}")

    try:
        results["message_linked_tasks"] = await test_message_linked_task_creation()
    except Exception as e:
        results["message_linked_tasks"] = {"success": False, "error": str(e)}
        print(f"✗ Message-linked tasks FAILED: {e}")

    try:
        results["continuous_updates"] = await test_continuous_task_ledger_updates()
    except Exception as e:
        results["continuous_updates"] = {"success": False, "error": str(e)}
        print(f"✗ Continuous updates FAILED: {e}")

    print("\n" + "="*60)
    all_passed = all(r.get("success", False) for r in results.values())
    print(f"VALIDATION RESULT: {'ALL PASSED' if all_passed else 'SOME FAILED'}")
    print("="*60 + "\n")

    return results


if __name__ == "__main__":
    asyncio.run(run_all_validations())
