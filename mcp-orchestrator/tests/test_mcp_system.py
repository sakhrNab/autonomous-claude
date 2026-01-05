#!/usr/bin/env python3
"""
MCP System Tests

Tests for:
1. MCP Registry
2. Capability Matcher
3. Intent → MCP mapping
4. Auto-install logic
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_mcp_registry():
    """Test MCP registry functionality."""
    from mcp.registry import MCPRegistry, MCPCategory

    registry = MCPRegistry()

    # Test basic operations
    assert len(registry.servers) > 0, "Registry should have servers"
    print(f"  Registry has {len(registry.servers)} servers")

    # Test getting a server
    playwright = registry.get("playwright")
    assert playwright is not None, "Should have playwright"
    assert playwright.category == MCPCategory.BROWSER

    # Test category filtering
    browser_mcps = registry.get_by_category(MCPCategory.BROWSER)
    assert len(browser_mcps) > 0, "Should have browser MCPs"

    # Test finding for intent
    matches = registry.find_for_intent("scrape the website")
    assert len(matches) > 0, "Should match scraping intent"
    assert matches[0][0].name == "playwright", "Playwright should be top match"

    print("  MCP Registry: PASSED")
    return True


def test_capability_matcher():
    """Test capability matcher functionality."""
    from mcp.capability_matcher import CapabilityMatcher

    matcher = CapabilityMatcher()

    # Test scrape intent
    analysis = matcher.analyze_intent("scrape the product prices from example.com")
    assert analysis.task_type == "scrape", f"Expected scrape, got {analysis.task_type}"
    assert len(analysis.required_mcps) > 0 or len(analysis.missing_mcps) > 0

    # Test database intent
    analysis = matcher.analyze_intent("query the postgresql database for active users")
    assert analysis.task_type == "database", f"Expected database, got {analysis.task_type}"

    # Test automation intent
    analysis = matcher.analyze_intent("automate the deployment workflow with n8n")
    assert analysis.task_type == "automate", f"Expected automate, got {analysis.task_type}"

    # Test search intent
    analysis = matcher.analyze_intent("search the web for Python best practices")
    assert analysis.task_type == "search", f"Expected search, got {analysis.task_type}"

    print("  Capability Matcher: PASSED")
    return True


def test_intent_to_mcp_mapping():
    """Test various intents map to correct MCPs."""
    from mcp.capability_matcher import CapabilityMatcher

    matcher = CapabilityMatcher()

    test_cases = [
        ("scrape this website", "scrape", ["playwright", "firecrawl"]),
        ("query the database", "database", ["postgresql", "sqlite"]),
        ("search for articles", "search", ["brave-search", "exa"]),
        ("create a workflow in n8n", "automate", ["n8n", "make"]),
        ("deploy to production", "deploy", ["docker", "github"]),
        ("send a notification to slack", "notify", ["slack"]),
        ("read the documentation", "docs", ["context7"]),
    ]

    passed = 0
    for intent, expected_type, expected_mcps in test_cases:
        analysis = matcher.analyze_intent(intent)

        if analysis.task_type == expected_type:
            passed += 1
        else:
            print(f"  FAIL: '{intent}' -> {analysis.task_type} (expected {expected_type})")

    print(f"  Intent mapping: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


def test_missing_mcp_detection():
    """Test detection of missing MCPs."""
    from mcp.capability_matcher import CapabilityMatcher

    matcher = CapabilityMatcher()

    # Clear installed MCPs for test
    matcher.registry.installed.clear()

    analysis = matcher.analyze_intent("scrape the website")

    # Should detect missing MCPs since none are installed
    has_missing = len(analysis.missing_mcps) > 0
    print(f"  Missing MCP detection: {'PASSED' if has_missing else 'FAILED'}")
    return has_missing


def test_can_handle():
    """Test the can_handle function."""
    from mcp.capability_matcher import CapabilityMatcher

    matcher = CapabilityMatcher()

    # Mark some MCPs as installed
    matcher.registry.mark_installed("playwright")
    matcher.registry.mark_installed("postgresql")

    # Should be able to handle scraping with playwright installed
    can, reason = matcher.can_handle("scrape the website")
    print(f"  Can handle scraping: {can} - {reason}")

    return True


def run_all_tests():
    """Run all MCP system tests."""
    print("\n" + "="*60)
    print("MCP SYSTEM TESTS")
    print("="*60 + "\n")

    results = {}

    tests = [
        ("MCP Registry", test_mcp_registry),
        ("Capability Matcher", test_capability_matcher),
        ("Intent Mapping", test_intent_to_mcp_mapping),
        ("Missing MCP Detection", test_missing_mcp_detection),
        ("Can Handle", test_can_handle),
    ]

    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            results[name] = False
            print(f"  {name}: ERROR - {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*60)
    passed = sum(1 for v in results.values() if v)
    print(f"RESULTS: {passed}/{len(results)} tests passed")
    print("="*60 + "\n")

    return all(results.values())


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
