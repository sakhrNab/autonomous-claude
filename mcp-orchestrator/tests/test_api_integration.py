#!/usr/bin/env python3
"""
API Integration Test - Tests orchestration via HTTP API.
"""

import asyncio
import httpx
import json
import time

API_BASE = "http://localhost:8000"


async def test_api_task():
    """Test submitting a task via the API."""
    print("\n" + "=" * 60)
    print("API INTEGRATION TEST")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=120.0) as client:
        # Test 1: Health check
        print("\n[1] Testing API health...")
        try:
            resp = await client.get(f"{API_BASE}/")
            print(f"    Status: {resp.status_code}")
            if resp.status_code == 200:
                print("    PASS: API is running")
            else:
                print("    FAIL: API not responding correctly")
                return
        except Exception as e:
            print(f"    FAIL: Cannot connect to API - {e}")
            print("\n    Please start the server first:")
            print("    cd mcp-orchestrator && python -m api.server")
            return

        # Test 2: Submit a simple task
        print("\n[2] Submitting test task...")
        task_data = {
            "intent": "What is 2+2? Just answer with the number.",
            "priority": "normal"
        }

        try:
            resp = await client.post(
                f"{API_BASE}/api/task",
                json=task_data
            )
            print(f"    Status: {resp.status_code}")
            result = resp.json()
            print(f"    Response: {json.dumps(result, indent=2)}")

            if "task_id" in result:
                task_id = result["task_id"]
                print(f"    Task ID: {task_id}")
                print("    PASS: Task submitted")

                # Wait for execution
                print("\n[3] Waiting for task execution...")
                for i in range(30):
                    await asyncio.sleep(2)
                    status_resp = await client.get(f"{API_BASE}/api/tasks/{task_id}")
                    task_data = status_resp.json()
                    current_state = task_data.get("state", "unknown")
                    print(f"    [{i+1}] State: {current_state}")

                    if current_state in ["completed", "done", "error", "blocked"]:
                        print(f"\n    Final result:")
                        print(json.dumps(task_data, indent=2))
                        break
                else:
                    print("    TIMEOUT waiting for task")

        except Exception as e:
            import traceback
            print(f"    FAIL: {e}")
            traceback.print_exc()

        # Test 3: Submit a job scraping task
        print("\n[4] Submitting job scraping task...")
        job_task = {
            "intent": "Find 3 software engineering jobs from gulftalent.com",
            "priority": "normal"
        }

        try:
            resp = await client.post(
                f"{API_BASE}/api/task",
                json=job_task
            )
            result = resp.json()
            print(f"    Task ID: {result.get('task_id', 'N/A')}")

            if "task_id" in result:
                task_id = result["task_id"]

                # Wait longer for job scraping
                print("\n[5] Waiting for job scraping (this may take a while)...")
                for i in range(60):
                    await asyncio.sleep(3)
                    status_resp = await client.get(f"{API_BASE}/api/tasks/{task_id}")
                    task_data = status_resp.json()
                    current_state = task_data.get("state", "unknown")
                    print(f"    [{i+1}] State: {current_state}")

                    if current_state in ["completed", "done", "error", "blocked"]:
                        print(f"\n    Final job scraping result:")

                        # Check for jobs in result
                        task_result = task_data.get("result", {})
                        if isinstance(task_result, dict):
                            jobs = task_result.get("jobs", [])
                            if jobs:
                                print(f"    Found {len(jobs)} jobs:")
                                for job in jobs[:3]:
                                    print(f"\n      Title: {job.get('title', 'N/A')}")
                                    print(f"      URL: {job.get('url', 'N/A')}")
                                    reqs = job.get("requirements", [])
                                    if reqs:
                                        print(f"      Requirements: {reqs[:3]}")
                                    else:
                                        print("      Requirements: EMPTY (this is the issue!)")
                            else:
                                print("    No jobs in result - checking raw result...")
                                print(json.dumps(task_result, indent=2)[:2000])

                        # Check hooks fired
                        hooks = task_data.get("hooks_fired", [])
                        if hooks:
                            print(f"\n    Hooks fired: {hooks}")

                        break
                else:
                    print("    TIMEOUT waiting for job scraping")

        except Exception as e:
            import traceback
            print(f"    FAIL: {e}")
            traceback.print_exc()


if __name__ == "__main__":
    print("Testing orchestration via API...")
    print("Make sure the server is running: python -m api.server")
    asyncio.run(test_api_task())
