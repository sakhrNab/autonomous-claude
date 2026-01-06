"""
SDK Orchestrator - Main entry point for SDK usage.
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable


class Orchestrator:
    """
    Main SDK class for using the Autonomous Operator in other projects.

    Example:
        orchestrator = Orchestrator(project_path="./my-app")
        await orchestrator.analyze_project()
        result = await orchestrator.run("Add user login")
    """

    def __init__(
        self,
        project_path: str = ".",
        server_url: str = "http://localhost:8000",
        auto_start_server: bool = False,
    ):
        """
        Initialize the orchestrator.

        Args:
            project_path: Path to your project (for codebase analysis)
            server_url: URL of running orchestrator server
            auto_start_server: Whether to start the server if not running
        """
        self.project_path = Path(project_path).resolve()
        self.server_url = server_url
        self.auto_start_server = auto_start_server
        self._server_process = None
        self._project_context = {}

    async def start(self) -> bool:
        """Start the orchestrator server if needed."""
        if await self._check_server():
            return True

        if self.auto_start_server:
            return await self._start_server()

        return False

    async def stop(self):
        """Stop the orchestrator server if we started it."""
        if self._server_process:
            self._server_process.terminate()
            await self._server_process.wait()
            self._server_process = None

    async def _check_server(self) -> bool:
        """Check if server is running."""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.server_url}/api/tasks", timeout=2.0)
                return response.status_code == 200
        except:
            return False

    async def _start_server(self) -> bool:
        """Start the orchestrator server."""
        sdk_path = Path(__file__).parent.parent
        server_script = sdk_path / "api" / "server.py"

        if not server_script.exists():
            raise FileNotFoundError(f"Server script not found: {server_script}")

        self._server_process = await asyncio.create_subprocess_exec(
            sys.executable,
            str(server_script),
            cwd=str(sdk_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Wait for server to start
        await asyncio.sleep(3)
        return await self._check_server()

    async def analyze_project(self) -> Dict[str, Any]:
        """
        Analyze the project codebase to understand its structure.

        This helps the orchestrator make better decisions about
        how to implement features in your project.
        """
        import httpx

        analysis = {
            "project_path": str(self.project_path),
            "files": [],
            "languages": set(),
            "frameworks": [],
            "structure": {},
        }

        # Scan project files
        for ext in [".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java"]:
            files = list(self.project_path.rglob(f"*{ext}"))
            if files:
                analysis["languages"].add(ext[1:])
                analysis["files"].extend([str(f.relative_to(self.project_path)) for f in files[:100]])

        # Detect frameworks
        if (self.project_path / "package.json").exists():
            analysis["frameworks"].append("node")
        if (self.project_path / "requirements.txt").exists():
            analysis["frameworks"].append("python")
        if (self.project_path / "go.mod").exists():
            analysis["frameworks"].append("go")
        if (self.project_path / "Cargo.toml").exists():
            analysis["frameworks"].append("rust")

        analysis["languages"] = list(analysis["languages"])
        self._project_context = analysis

        return analysis

    async def run(self, task: str, context: Dict = None) -> Dict[str, Any]:
        """
        Execute any task using the orchestrator.

        Args:
            task: Natural language description of what to do
            context: Optional additional context

        Returns:
            Execution result with answer and metadata
        """
        import httpx

        if not await self._check_server():
            if self.auto_start_server:
                await self.start()
            else:
                raise ConnectionError(f"Orchestrator server not running at {self.server_url}")

        # Merge project context with provided context
        full_context = {**self._project_context, **(context or {})}

        async with httpx.AsyncClient() as client:
            # Submit task
            response = await client.post(
                f"{self.server_url}/api/task",
                json={"intent": task, "context": full_context},
                timeout=10.0,
            )
            task_data = response.json()
            task_id = task_data.get("task_id")

            if not task_id:
                return {"success": False, "error": "Failed to create task"}

            # Poll for completion
            for _ in range(120):  # 2 minute timeout
                await asyncio.sleep(1)
                status_response = await client.get(
                    f"{self.server_url}/api/tasks/{task_id}",
                    timeout=30.0,
                )
                status = status_response.json()

                if status.get("state") == "completed":
                    return {
                        "success": True,
                        "task_id": task_id,
                        "result": status.get("result", {}),
                    }
                elif status.get("state") == "blocked":
                    return {
                        "success": False,
                        "task_id": task_id,
                        "error": status.get("result", {}).get("error", "Task blocked"),
                    }

            return {"success": False, "error": "Task timeout"}

    # Convenience methods for specific agents

    async def code(self, task: str) -> Dict[str, Any]:
        """Execute a coding task."""
        return await self.run(f"/code {task}")

    async def api(self, task: str) -> Dict[str, Any]:
        """Create or modify APIs."""
        return await self.run(f"/api {task}")

    async def db(self, task: str) -> Dict[str, Any]:
        """Database operations."""
        return await self.run(f"/db {task}")

    async def test(self, task: str = "Run all tests") -> Dict[str, Any]:
        """Run tests."""
        return await self.run(f"/test {task}")

    async def scrape(self, url_or_task: str) -> Dict[str, Any]:
        """Scrape a website."""
        if "scrape" not in url_or_task.lower():
            url_or_task = f"Scrape content from {url_or_task}"
        return await self.run(url_or_task)

    async def search(self, query: str) -> Dict[str, Any]:
        """Search the web."""
        return await self.run(f"Search for {query}")

    async def plan(self, task: str) -> Dict[str, Any]:
        """Get an execution plan without executing."""
        return await self.run(f"/plan {task}")


# Synchronous wrapper for non-async code
class SyncOrchestrator:
    """Synchronous wrapper for the Orchestrator."""

    def __init__(self, *args, **kwargs):
        self._async_orchestrator = Orchestrator(*args, **kwargs)

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def analyze_project(self):
        return self._run(self._async_orchestrator.analyze_project())

    def run(self, task: str, context: Dict = None):
        return self._run(self._async_orchestrator.run(task, context))

    def code(self, task: str):
        return self._run(self._async_orchestrator.code(task))

    def api(self, task: str):
        return self._run(self._async_orchestrator.api(task))

    def db(self, task: str):
        return self._run(self._async_orchestrator.db(task))

    def test(self, task: str = "Run all tests"):
        return self._run(self._async_orchestrator.test(task))

    def scrape(self, url_or_task: str):
        return self._run(self._async_orchestrator.scrape(url_or_task))

    def search(self, query: str):
        return self._run(self._async_orchestrator.search(query))
