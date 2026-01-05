"""
MCP Orchestrator - Main Entry Point

Run the autonomous MCP orchestrator system.
"""

import asyncio
import argparse
import sys
from pathlib import Path

from core import MCPOrchestrator, WorkflowEngine, Config


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Autonomous MCP Orchestrator"
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to configuration file",
    )
    parser.add_argument(
        "--intent",
        type=str,
        help="Intent to execute",
    )
    parser.add_argument(
        "--user",
        type=str,
        default="default_user",
        help="User ID",
    )
    parser.add_argument(
        "--budget",
        type=float,
        default=100.0,
        help="Budget limit in USD",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode (no actual execution)",
    )

    args = parser.parse_args()

    # Load configuration
    if args.config and Path(args.config).exists():
        config = Config.load_from_file(args.config)
    else:
        config = Config.load_from_env()

    # Validate configuration
    errors = config.validate()
    if errors:
        print("Configuration errors:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)

    # Create orchestrator
    workflow_engine = WorkflowEngine(config)

    if not args.intent:
        print("No intent provided. Use --intent to specify what to execute.")
        print("\nExample:")
        print('  python main.py --intent "Deploy the application and run tests"')
        sys.exit(0)

    print(f"Starting MCP Orchestrator...")
    print(f"Intent: {args.intent}")
    print(f"User: {args.user}")
    print(f"Budget: ${args.budget}")
    print("-" * 50)

    # Execute
    result = await workflow_engine.execute_workflow(
        user_id=args.user,
        intent=args.intent,
        options={"budget_limit": args.budget},
    )

    # Print results
    print("\n" + "=" * 50)
    if result.get("success"):
        print("EXECUTION COMPLETED SUCCESSFULLY")
        print(f"Workflow ID: {result.get('workflow_id')}")
        print(f"Session ID: {result.get('session_id')}")

        if result.get("result"):
            r = result["result"]
            print(f"Iterations: {r.get('iterations', 'N/A')}")
            print(f"Elapsed: {r.get('elapsed_seconds', 0):.1f} seconds")
            print(f"Budget spent: ${r.get('budget_spent', 0):.2f}")
    else:
        print("EXECUTION FAILED")
        print(f"Error: {result.get('error')}")

    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
