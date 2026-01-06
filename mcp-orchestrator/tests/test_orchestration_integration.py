#!/usr/bin/env python3
"""
Orchestration Integration Test

Tests that all components work together:
1. Main Orchestrator routes the task
2. Source of Truth provides routing info
3. Planning Agent creates a plan
4. Hooks fire (BEFORE/AFTER)
5. Execution Engine uses intelligent orchestrator
6. Results include proper data structure
"""

import asyncio
import sys
import os
from pathlib import Path

# Add mcp-orchestrator directory to path for direct imports
mcp_dir = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(mcp_dir))
os.chdir(mcp_dir)  # Change to mcp dir for relative path resolution


async def test_full_orchestration_flow():
    """Test the complete orchestration flow."""
    print("\n" + "=" * 60)
    print("ORCHESTRATION INTEGRATION TEST")
    print("=" * 60 + "\n")

    results = {
        "main_orchestrator_import": False,
        "source_of_truth_routing": False,
        "planning_agent_plan": False,
        "hook_system_fire": False,
        "execution_engine_run": False,
        "result_has_promise": False,
        "hooks_were_fired": False,
    }

    # Test 1: Import main orchestrator
    print("[1] Testing main orchestrator import...")
    try:
        # Import directly from files, not from package
        import importlib.util

        # Load main_orchestrator module directly
        spec = importlib.util.spec_from_file_location(
            "main_orchestrator",
            mcp_dir / "core" / "main_orchestrator.py"
        )
        main_orchestrator_module = importlib.util.module_from_spec(spec)
        sys.modules["main_orchestrator"] = main_orchestrator_module
        spec.loader.exec_module(main_orchestrator_module)

        get_main_orchestrator = main_orchestrator_module.get_main_orchestrator
        OrchestrationResult = main_orchestrator_module.OrchestrationResult

        orchestrator = get_main_orchestrator()
        results["main_orchestrator_import"] = True
        print("    PASS: Main orchestrator imported successfully")
    except Exception as e:
        import traceback
        print(f"    FAIL: {e}")
        traceback.print_exc()
        return results

    # Test 2: Source of Truth routing
    print("\n[2] Testing Source of Truth routing...")
    try:
        test_request = "scrape 3 software engineering jobs from gulftalent.com"
        routing = orchestrator.source_of_truth.route_task(test_request)
        print(f"    Routing result: {routing}")
        if routing.get("category") or routing.get("capabilities"):
            results["source_of_truth_routing"] = True
            print("    PASS: Source of Truth returned routing info")
        else:
            print("    WARN: Routing info seems incomplete")
    except Exception as e:
        print(f"    FAIL: {e}")

    # Test 3: Planning Agent
    print("\n[3] Testing Planning Agent...")
    try:
        plan = await orchestrator.planning_agent.analyze_and_plan(test_request, {})
        print(f"    Plan category: {plan.category}")
        print(f"    Plan steps: {len(plan.steps)}")
        print(f"    Understood goal: {plan.understood_goal}")
        if plan.steps:
            results["planning_agent_plan"] = True
            print("    PASS: Planning Agent created a plan")
            for step in plan.steps:
                print(f"      - Step {step.number}: {step.description} ({step.capability_type})")
        else:
            print("    WARN: Plan has no steps")
    except Exception as e:
        print(f"    FAIL: {e}")

    # Test 4: Hook System
    print("\n[4] Testing Hook System...")
    try:
        from hooks.hook_system import HookTrigger
        hooks = orchestrator.hook_system
        test_hooks = ["check-design-patterns", "load-design-system"]
        before_results = await hooks.trigger(
            HookTrigger.BEFORE,
            test_hooks,
            {"task_request": test_request}
        )
        print(f"    BEFORE hooks triggered: {len(before_results)}")
        for hr in before_results:
            print(f"      - {hr.hook_name}: {'SUCCESS' if hr.success else 'FAIL'}")
        results["hook_system_fire"] = True
        print("    PASS: Hook system works")
    except Exception as e:
        print(f"    FAIL: {e}")

    # Test 5: Full orchestration (simplified request)
    print("\n[5] Testing Full Orchestration...")
    print("    Request: 'What is 2+2?'")
    try:
        simple_result = await orchestrator.orchestrate("What is 2+2?", {})
        print(f"    Task ID: {simple_result.task_id}")
        print(f"    Promise: {simple_result.promise}")
        print(f"    Status: {simple_result.status}")
        print(f"    Hooks fired: {simple_result.hooks_fired}")

        if simple_result.promise:
            results["result_has_promise"] = True
            print("    PASS: Result has promise")

        if simple_result.hooks_fired:
            results["hooks_were_fired"] = True
            print("    PASS: Hooks were fired")

        results["execution_engine_run"] = True
        print("    PASS: Orchestration completed")

    except Exception as e:
        import traceback
        print(f"    FAIL: {e}")
        traceback.print_exc()

    # Summary
    print("\n" + "=" * 60)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"RESULTS: {passed}/{total} tests passed")
    print("=" * 60)

    for name, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {name}")

    return results


async def test_job_scraping_task():
    """Test a real job scraping task."""
    print("\n" + "=" * 60)
    print("JOB SCRAPING TASK TEST")
    print("=" * 60 + "\n")

    try:
        from core.main_orchestrator import get_main_orchestrator
        orchestrator = get_main_orchestrator()

        task = "Find 3 software engineering jobs from gulftalent.com"
        print(f"Task: {task}")
        print("-" * 40)

        result = await orchestrator.orchestrate(task, {})

        print(f"\nTask ID: {result.task_id}")
        print(f"Promise: {result.promise}")
        print(f"Status: {result.status}")
        print(f"Message: {result.message}")

        if result.hooks_fired:
            print(f"\nHooks Fired ({len(result.hooks_fired)}):")
            for hook in result.hooks_fired:
                print(f"  - {hook}")

        if result.plan:
            print(f"\nPlan:")
            print(f"  Category: {result.plan.get('category')}")
            print(f"  Goal: {result.plan.get('understood_goal')}")
            steps = result.plan.get('steps', [])
            print(f"  Steps ({len(steps)}):")
            for step in steps:
                print(f"    {step.get('number')}. {step.get('description')}")

        if result.results:
            print(f"\nResults ({len(result.results)}):")
            for i, r in enumerate(result.results):
                print(f"\n  Result {i + 1}:")
                if isinstance(r, dict):
                    if r.get("jobs"):
                        print(f"    Jobs found: {len(r.get('jobs', []))}")
                        for job in r.get("jobs", [])[:3]:
                            print(f"      - {job.get('title', 'N/A')}")
                            if job.get("requirements"):
                                print(f"        Requirements: {job.get('requirements')[:2]}")
                    else:
                        for key, value in r.items():
                            if isinstance(value, str) and len(value) > 100:
                                value = value[:100] + "..."
                            print(f"    {key}: {value}")

        return result

    except Exception as e:
        import traceback
        print(f"ERROR: {e}")
        traceback.print_exc()
        return None


if __name__ == "__main__":
    print("Starting orchestration integration tests...\n")

    # Run integration tests
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        # Basic integration tests
        results = loop.run_until_complete(test_full_orchestration_flow())

        # Only run job scraping if basic tests pass
        if results.get("execution_engine_run"):
            print("\n\nRunning job scraping task test...")
            loop.run_until_complete(test_job_scraping_task())
        else:
            print("\nSkipping job scraping test - basic tests failed")

    finally:
        loop.close()
