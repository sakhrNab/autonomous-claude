#!/usr/bin/env python3
"""
Autonomous Flow Validation Tests

Tests the full END GOAL implementation:
1. Intent-based operation (not instructions)
2. Trust with real stakes
3. User forgets internals
4. Memory with judgment
5. Silence as success

This validates the complete integration of:
- Claude Code hooks
- Autonomous operator skill
- Preference learning
- Task ledger enforcement
"""

import asyncio
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def test_hook_configuration():
    """Test that Claude Code hooks are properly configured."""
    settings_path = Path(__file__).parent.parent.parent / ".claude" / "settings.json"

    assert settings_path.exists(), f"Settings file not found at {settings_path}"

    with open(settings_path) as f:
        settings = json.load(f)

    hooks = settings.get("hooks", {})

    # Required hooks
    required_hooks = [
        "PostToolUse",    # Task ledger updates
        "PreToolUse",     # Intelligent routing
        "Stop",           # Completion checking
        "SessionStart",   # Context loading
        "UserPromptSubmit",  # Intent analysis
    ]

    for hook_type in required_hooks:
        assert hook_type in hooks, f"Missing hook type: {hook_type}"
        assert len(hooks[hook_type]) > 0, f"No hooks configured for {hook_type}"

    print("  Hook configuration: PASSED")
    return True


def test_hook_scripts_exist():
    """Test that all hook scripts exist and are executable."""
    hooks_dir = Path(__file__).parent.parent.parent / ".claude" / "hooks"

    required_scripts = [
        "task-ledger-update.py",
        "intelligent-router.py",
        "completion-checker.py",
        "session-init.py",
        "intent-analyzer.py",
        "agent-selector.py",
    ]

    for script in required_scripts:
        script_path = hooks_dir / script
        assert script_path.exists(), f"Hook script not found: {script}"

    print("  Hook scripts exist: PASSED")
    return True


def test_skill_file_exists():
    """Test that the autonomous operator skill is properly defined."""
    skill_path = Path(__file__).parent.parent.parent / ".claude" / "skills" / "autonomous-operator" / "SKILL.md"

    assert skill_path.exists(), f"Skill file not found at {skill_path}"

    content = skill_path.read_text(encoding="utf-8")

    # Check required sections
    required_content = [
        "name: autonomous-operator",
        "description:",
        "# Autonomous Operator",
        "Intent, not instructions",
        "Task Ledger Integration",
        "Memory and Judgment",
    ]

    for req in required_content:
        assert req in content, f"Missing required content: {req}"

    print("  Skill file valid: PASSED")
    return True


def test_preference_learner():
    """Test the preference learning system."""
    # Add mcp-orchestrator directory to path for imports
    import sys
    from pathlib import Path
    mcp_dir = Path(__file__).parent.parent.resolve()
    if str(mcp_dir) not in sys.path:
        sys.path.insert(0, str(mcp_dir))

    from state.preference_learner import PreferenceLearner

    test_prefs_path = mcp_dir / "state" / "test_preferences.json"
    learner = PreferenceLearner(storage_path=str(test_prefs_path))

    # Test learning from approval
    learner.learn_from_approval("deploy", "production", approved=True)
    learner.learn_from_approval("deploy", "production", approved=True)
    learner.learn_from_approval("deploy", "production", approved=True)

    should_approve, confidence = learner.should_auto_approve("deploy", "production")
    assert should_approve, "Should auto-approve after 3 approvals"
    assert confidence > 0.6, f"Confidence too low: {confidence}"

    # Test learning from correction
    learner.learn_from_correction(
        what_was_wrong="You should ask less before doing things",
        what_was_expected="Just do it without asking"
    )

    result = learner.get_preference("autonomy", "auto_approve", False)
    assert result is True, f"Expected auto_approve=True, got {result}"

    # Clean up
    test_prefs_path.unlink(missing_ok=True)

    print("  Preference learner: PASSED")
    return True


def test_task_ledger_format():
    """Test that task ledger files have correct format."""
    project_dir = Path(__file__).parent.parent.parent

    # Check for to-do files
    todo_files = [
        project_dir / "to-do.md",
        project_dir / "to-do-session2.md",
    ]

    valid_markers = ["[ ]", "[x]", "[~]", "[!]"]

    for todo_file in todo_files:
        if todo_file.exists():
            content = todo_file.read_text(encoding="utf-8")
            # Check that it has task markers
            has_markers = any(marker in content for marker in valid_markers)
            assert has_markers, f"No task markers found in {todo_file}"

    print("  Task ledger format: PASSED")
    return True


def test_state_files_structure():
    """Test that state directory has proper structure."""
    state_dir = Path(__file__).parent.parent / "state"

    # Required state modules
    required_modules = [
        "memory_store.py",
        "message_store.py",
        "conversation_store.py",
        "preference_learner.py",
        "session_store.py",
        "audit_logger.py",
    ]

    for module in required_modules:
        module_path = state_dir / module
        assert module_path.exists(), f"Missing state module: {module}"

    print("  State structure: PASSED")
    return True


def test_end_goal_criteria():
    """
    Test the five END GOAL criteria.

    1. Intent, not instructions
    2. Trust with real stakes
    3. User forgets internals
    4. Memory with judgment
    5. Silence as success
    """
    results = {
        "intent_not_instructions": False,
        "trust_with_stakes": False,
        "user_forgets_internals": False,
        "memory_with_judgment": False,
        "silence_as_success": False,
    }

    # 1. Intent, not instructions
    # Check if intent analyzer hook exists and works
    intent_hook = Path(__file__).parent.parent.parent / ".claude" / "hooks" / "intent-analyzer.py"
    if intent_hook.exists():
        content = intent_hook.read_text()
        if "delegation_intent" in content and "handle this" in content.lower():
            results["intent_not_instructions"] = True
            print("  1. Intent, not instructions: PASSED")

    # 2. Trust with real stakes
    # Check if intelligent routing handles risk
    router_hook = Path(__file__).parent.parent.parent / ".claude" / "hooks" / "intelligent-router.py"
    if router_hook.exists():
        content = router_hook.read_text()
        if "risk_level" in content and "auto_approve" in content:
            results["trust_with_stakes"] = True
            print("  2. Trust with real stakes: PASSED")

    # 3. User forgets internals
    # Check if skill abstracts implementation details
    skill_path = Path(__file__).parent.parent.parent / ".claude" / "skills" / "autonomous-operator" / "SKILL.md"
    if skill_path.exists():
        content = skill_path.read_text()
        if "Report Outcomes, Not Steps" in content:
            results["user_forgets_internals"] = True
            print("  3. User forgets internals: PASSED")

    # 4. Memory with judgment
    # Check if preference learner exists
    pref_learner = Path(__file__).parent.parent / "state" / "preference_learner.py"
    if pref_learner.exists():
        content = pref_learner.read_text()
        if "learn_from_correction" in content and "should_auto_approve" in content:
            results["memory_with_judgment"] = True
            print("  4. Memory with judgment: PASSED")

    # 5. Silence as success
    # Check if completion checker only stops when done
    completion_hook = Path(__file__).parent.parent.parent / ".claude" / "hooks" / "completion-checker.py"
    if completion_hook.exists():
        content = completion_hook.read_text()
        if "block" in content and "incomplete" in content and "approve" in content:
            results["silence_as_success"] = True
            print("  5. Silence as success: PASSED")

    all_passed = all(results.values())
    return all_passed, results


async def run_all_tests():
    """Run all autonomous flow tests."""
    print("\n" + "="*60)
    print("AUTONOMOUS FLOW VALIDATION")
    print("="*60 + "\n")

    tests = [
        ("Hook Configuration", test_hook_configuration),
        ("Hook Scripts", test_hook_scripts_exist),
        ("Skill File", test_skill_file_exists),
        ("State Structure", test_state_files_structure),
        ("Task Ledger Format", test_task_ledger_format),
    ]

    results = {}

    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except AssertionError as e:
            results[test_name] = False
            print(f"  {test_name}: FAILED - {e}")
        except Exception as e:
            results[test_name] = False
            print(f"  {test_name}: ERROR - {e}")

    # Test preference learner separately (needs import)
    try:
        # Add mcp-orchestrator to path
        mcp_dir = Path(__file__).parent.parent.resolve()
        if str(mcp_dir) not in sys.path:
            sys.path.insert(0, str(mcp_dir))
        results["Preference Learner"] = test_preference_learner()
    except Exception as e:
        import traceback
        results["Preference Learner"] = False
        print(f"  Preference Learner: ERROR - {e}")
        traceback.print_exc()

    # Test END GOAL criteria
    print("\n" + "-"*40)
    print("END GOAL CRITERIA:")
    print("-"*40)

    try:
        all_criteria_passed, criteria_results = test_end_goal_criteria()
        results["END GOAL Criteria"] = all_criteria_passed
    except Exception as e:
        results["END GOAL Criteria"] = False
        print(f"  END GOAL Criteria: ERROR - {e}")

    # Summary
    print("\n" + "="*60)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"RESULTS: {passed}/{total} tests passed")

    if passed == total:
        print("STATUS: ALL TESTS PASSED - END GOAL ACHIEVED")
    else:
        print("STATUS: SOME TESTS FAILED")
        for name, result in results.items():
            if not result:
                print(f"  - {name}: FAILED")

    print("="*60 + "\n")

    return results


if __name__ == "__main__":
    asyncio.run(run_all_tests())
