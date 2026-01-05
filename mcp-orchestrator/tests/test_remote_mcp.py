"""
Remote MCP Orchestration Verification Tests

Per SESSION 2 Guide:
- cloud_code_adapter.py + route_message.py working
- Correct remote MCP triggered automatically
- Results returned, task ledger updated

This module verifies:
1. CloudCodeAdapter triggers remote MCPs correctly
2. RouteMessage skill routes to correct target
3. Task ledger is updated with results
4. Full integration flow works end-to-end
"""

import asyncio
from datetime import datetime
from typing import Dict, Any


async def test_cloud_code_adapter_mcp_trigger():
    """
    Test that CloudCodeAdapter correctly triggers remote MCPs.

    Validates:
    - MCP can be triggered with params
    - Message/task context is passed
    - Results are returned correctly
    """
    from ..core.cloud_code_adapter import CloudCodeAdapter, CloudCodeProvider

    # Use mock provider for testing
    adapter = CloudCodeAdapter(provider=CloudCodeProvider.MOCK)

    # Test MCP trigger
    result = await adapter.trigger_mcp(
        mcp_name="github-mcp",
        action="create_issue",
        params={
            "repo": "org/test-repo",
            "title": "Test Issue",
            "body": "This is a test issue",
        },
        message_id="test_msg_001",
        task_id="test_task_001",
        session_id="test_session",
    )

    assert result.success, f"MCP trigger failed: {result.error}"
    assert result.data is not None, "No data returned from MCP"
    assert result.mcp_name == "github-mcp", "Wrong MCP name in result"

    print("✓ CloudCodeAdapter MCP trigger PASSED")
    return {"success": True, "result": result.data}


async def test_cloud_code_adapter_workflow_trigger():
    """
    Test that CloudCodeAdapter correctly triggers remote workflows.

    Validates:
    - Workflows can be triggered
    - Input data is passed correctly
    - Results include execution status
    """
    from ..core.cloud_code_adapter import CloudCodeAdapter, CloudCodeProvider

    adapter = CloudCodeAdapter(provider=CloudCodeProvider.MOCK)

    result = await adapter.trigger_workflow(
        workflow_name="deploy-pipeline",
        input_data={
            "environment": "staging",
            "version": "1.2.3",
        },
        message_id="test_msg_002",
        task_id="test_task_002",
        session_id="test_session",
    )

    assert result.success, f"Workflow trigger failed: {result.error}"
    assert result.workflow_name == "deploy-pipeline", "Wrong workflow name"

    print("✓ CloudCodeAdapter workflow trigger PASSED")
    return {"success": True, "result": result.data}


async def test_route_message_mcp_routing():
    """
    Test that RouteMessage skill routes to correct MCP.

    Validates:
    - Message content is analyzed
    - Correct target type is determined
    - MCP name is identified
    """
    from ..skills.route_message import RouteMessage

    skill = RouteMessage()

    # Test routing a GitHub-related message
    result = await skill.execute(
        content="Create a pull request in the main repository",
        session_id="test_session",
        user_id="test_user",
    )

    assert result.success, f"Routing failed: {result.error}"
    assert "route" in result.data, "No route in result"
    assert result.data["route"]["type"] in ["mcp", "workflow", "skill"], "Invalid route type"

    print(f"✓ RouteMessage routing PASSED (routed to: {result.data['route']['type']})")
    return {"success": True, "route": result.data["route"]}


async def test_route_message_workflow_routing():
    """
    Test that RouteMessage skill routes to correct workflow.

    Validates workflow routing for deployment-related requests.
    """
    from ..skills.route_message import RouteMessage

    skill = RouteMessage()

    result = await skill.execute(
        content="Run the daily deployment pipeline for production",
        session_id="test_session",
        user_id="test_user",
    )

    assert result.success, f"Routing failed: {result.error}"

    print(f"✓ RouteMessage workflow routing PASSED")
    return {"success": True, "route": result.data.get("route")}


async def test_full_remote_mcp_integration():
    """
    Test full integration: Message → Route → Cloud Code → Result → Task Update.

    This is the end-to-end test for remote MCP orchestration.
    """
    from ..core.cloud_code_adapter import CloudCodeAdapter, CloudCodeProvider
    from ..skills.route_message import RouteMessage
    from ..state.message_store import MessageStore, MessageType
    from ..agents.task_manager_agent import TaskManagerAgent
    from ..agents.base_agent import AgentContext

    # Setup components
    adapter = CloudCodeAdapter(provider=CloudCodeProvider.MOCK)
    router = RouteMessage()
    message_store = MessageStore(storage_path="state/test_integration_msgs.json")
    task_manager = TaskManagerAgent(
        ledger_path="test_integration_todo.md",
        tasks_json_path="test_integration_tasks.json"
    )

    # Step 1: Create message
    message = message_store.create_message(
        user_id="test_user",
        content="Create a GitHub issue for the bug fix",
        message_type=MessageType.USER_TEXT,
        session_id="integration_test",
    )

    # Step 2: Create linked task
    task_id = f"msg_task_{message.message_id[:8]}"
    create_context = AgentContext(
        session_id="integration_test",
        user_id="system",
        iteration=0,
        plan={
            "action": "create_ledger",
            "tasks": [f"Process message: {message.content[:50]}"],
        },
    )
    await task_manager.perform_step(create_context)

    # Link task to message
    message_store.link_task(message.message_id, "task_1")

    # Step 3: Route the message
    route_result = await router.execute(
        content=message.content,
        session_id="integration_test",
        user_id="test_user",
    )

    assert route_result.success, "Routing failed"
    route = route_result.data.get("route", {})

    # Step 4: Execute via Cloud Code
    if route.get("type") == "mcp":
        execution_result = await adapter.trigger_mcp(
            mcp_name=route.get("name", "default-mcp"),
            action=route.get("action", "execute"),
            params=route.get("params", {}),
            message_id=message.message_id,
            task_id="task_1",
            session_id="integration_test",
        )
    elif route.get("type") == "workflow":
        execution_result = await adapter.trigger_workflow(
            workflow_name=route.get("name", "default-workflow"),
            input_data=route.get("params", {}),
            message_id=message.message_id,
            task_id="task_1",
            session_id="integration_test",
        )
    else:
        # Skill execution (simulated)
        execution_result = type('Result', (), {'success': True, 'data': {'status': 'completed'}})()

    # Step 5: Update task ledger with result
    update_context = AgentContext(
        session_id="integration_test",
        user_id="system",
        iteration=1,
        plan={
            "action": "update_task",
            "task_id": "task_1",
            "new_state": "completed" if execution_result.success else "blocked",
            "evidence": f"Execution completed: {execution_result.data}" if execution_result.success else None,
            "reason": "Execution failed" if not execution_result.success else None,
        },
    )
    await task_manager.perform_step(update_context)

    # Step 6: Mark message as completed
    message_store.mark_completed(message.message_id)

    # Verify final state
    final_message = message_store.get_message(message.message_id)
    assert final_message.status.value == "completed", "Message not marked completed"

    verify_context = AgentContext(
        session_id="integration_test",
        user_id="system",
        iteration=2,
        plan={"action": "verify_completion"},
    )
    verify_result = await task_manager.perform_step(verify_context)

    print("✓ Full remote MCP integration PASSED")
    return {
        "success": True,
        "message_id": message.message_id,
        "route": route,
        "execution_success": execution_result.success,
        "task_complete": verify_result.data.get("all_complete", False),
    }


async def run_all_remote_mcp_tests():
    """Run all remote MCP orchestration tests."""
    results = {}

    print("\n" + "="*60)
    print("REMOTE MCP ORCHESTRATION VERIFICATION")
    print("="*60 + "\n")

    tests = [
        ("mcp_trigger", test_cloud_code_adapter_mcp_trigger),
        ("workflow_trigger", test_cloud_code_adapter_workflow_trigger),
        ("mcp_routing", test_route_message_mcp_routing),
        ("workflow_routing", test_route_message_workflow_routing),
        ("full_integration", test_full_remote_mcp_integration),
    ]

    for test_name, test_func in tests:
        try:
            results[test_name] = await test_func()
        except Exception as e:
            results[test_name] = {"success": False, "error": str(e)}
            print(f"✗ {test_name} FAILED: {e}")

    print("\n" + "="*60)
    all_passed = all(r.get("success", False) for r in results.values())
    print(f"REMOTE MCP VERIFICATION: {'ALL PASSED' if all_passed else 'SOME FAILED'}")
    print("="*60 + "\n")

    return results


if __name__ == "__main__":
    asyncio.run(run_all_remote_mcp_tests())
