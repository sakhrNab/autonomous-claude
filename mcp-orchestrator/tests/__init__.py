"""
MCP Orchestrator Tests Module

Contains validation tests for Session 2 functionality:
- Chat-Workflow-Chat loop validation
- Remote MCP orchestration verification
- Continuous task ledger update tests
"""

from .test_chat_workflow_loop import (
    test_chat_workflow_chat_loop,
    test_message_linked_task_creation,
    test_continuous_task_ledger_updates,
    run_all_validations,
)

from .test_remote_mcp import (
    test_cloud_code_adapter_mcp_trigger,
    test_cloud_code_adapter_workflow_trigger,
    test_route_message_mcp_routing,
    test_route_message_workflow_routing,
    test_full_remote_mcp_integration,
    run_all_remote_mcp_tests,
)

__all__ = [
    # Chat-Workflow tests
    "test_chat_workflow_chat_loop",
    "test_message_linked_task_creation",
    "test_continuous_task_ledger_updates",
    "run_all_validations",
    # Remote MCP tests
    "test_cloud_code_adapter_mcp_trigger",
    "test_cloud_code_adapter_workflow_trigger",
    "test_route_message_mcp_routing",
    "test_route_message_workflow_routing",
    "test_full_remote_mcp_integration",
    "run_all_remote_mcp_tests",
]
