"""
Testing Agent

The Testing Agent ensures that all tasks are properly tested before completion.

Responsibilities:
1. Detect test frameworks in the project
2. Run appropriate tests after code changes
3. Generate tests for new code
4. Verify test coverage
5. Report test results

No task is complete until tests pass!
"""

import asyncio
import json
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class TestResult:
    """Result of running tests."""
    success: bool
    tests_run: int
    tests_passed: int
    tests_failed: int
    tests_skipped: int
    duration_ms: int
    output: str
    failures: List[Dict[str, Any]]
    coverage: Optional[float] = None


class TestingAgent:
    """
    The Testing Agent - ensures all code is tested.

    This agent:
    - Detects the test framework used in the project
    - Runs tests after code changes
    - Can generate tests for new code
    - Reports coverage and failures
    """

    def __init__(self, project_path: Path = None):
        self.project_path = project_path or Path.cwd()
        self.claude_cli = shutil.which("claude")

        # Detect test framework
        self.test_framework = self._detect_test_framework()

    def _detect_test_framework(self) -> Dict[str, Any]:
        """Detect what test framework the project uses."""
        framework = {
            "name": None,
            "command": None,
            "config_file": None,
        }

        # Python projects
        if (self.project_path / "pytest.ini").exists() or \
           (self.project_path / "pyproject.toml").exists() or \
           (self.project_path / "setup.py").exists():
            # Check for pytest
            if any((self.project_path / "tests").glob("test_*.py")) or \
               any((self.project_path / "tests").glob("*_test.py")) or \
               any(self.project_path.glob("test_*.py")):
                framework["name"] = "pytest"
                framework["command"] = "pytest -v --tb=short"
                return framework

        # JavaScript/TypeScript projects
        package_json = self.project_path / "package.json"
        if package_json.exists():
            try:
                pkg = json.loads(package_json.read_text())
                scripts = pkg.get("scripts", {})

                if "test" in scripts:
                    framework["name"] = "npm"
                    framework["command"] = "npm test"

                    # Detect specific framework
                    test_cmd = scripts.get("test", "")
                    if "jest" in test_cmd:
                        framework["name"] = "jest"
                    elif "vitest" in test_cmd:
                        framework["name"] = "vitest"
                    elif "mocha" in test_cmd:
                        framework["name"] = "mocha"

                    return framework
            except:
                pass

        # Go projects
        if any(self.project_path.glob("*_test.go")):
            framework["name"] = "go"
            framework["command"] = "go test ./..."
            return framework

        # Rust projects
        if (self.project_path / "Cargo.toml").exists():
            framework["name"] = "cargo"
            framework["command"] = "cargo test"
            return framework

        return framework

    async def run_tests(
        self,
        files_changed: List[str] = None,
        test_filter: str = None,
        with_coverage: bool = False
    ) -> TestResult:
        """
        Run tests for the project.

        Args:
            files_changed: List of files that changed (to run related tests)
            test_filter: Filter to run specific tests
            with_coverage: Run with coverage report

        Returns:
            TestResult with success status and details
        """
        start = datetime.now()

        if not self.test_framework.get("name"):
            return TestResult(
                success=True,
                tests_run=0,
                tests_passed=0,
                tests_failed=0,
                tests_skipped=0,
                duration_ms=0,
                output="No test framework detected",
                failures=[],
            )

        command = self.test_framework["command"]

        # Add coverage if requested
        if with_coverage:
            if self.test_framework["name"] == "pytest":
                command = "pytest -v --tb=short --cov=."
            elif self.test_framework["name"] == "jest":
                command = "npm test -- --coverage"

        # Add filter if specified
        if test_filter:
            if self.test_framework["name"] == "pytest":
                command = f"{command} -k '{test_filter}'"
            elif self.test_framework["name"] in ["jest", "vitest"]:
                command = f"npm test -- --testNamePattern='{test_filter}'"

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=str(self.project_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=300  # 5 minute timeout
            )

            output = stdout.decode("utf-8") + stderr.decode("utf-8")
            duration = int((datetime.now() - start).total_seconds() * 1000)

            # Parse results
            parsed = self._parse_test_output(output, self.test_framework["name"])

            return TestResult(
                success=process.returncode == 0,
                tests_run=parsed.get("tests_run", 0),
                tests_passed=parsed.get("tests_passed", 0),
                tests_failed=parsed.get("tests_failed", 0),
                tests_skipped=parsed.get("tests_skipped", 0),
                duration_ms=duration,
                output=output,
                failures=parsed.get("failures", []),
                coverage=parsed.get("coverage"),
            )

        except asyncio.TimeoutError:
            return TestResult(
                success=False,
                tests_run=0,
                tests_passed=0,
                tests_failed=0,
                tests_skipped=0,
                duration_ms=300000,
                output="Tests timed out after 5 minutes",
                failures=[{"error": "Timeout"}],
            )
        except Exception as e:
            return TestResult(
                success=False,
                tests_run=0,
                tests_passed=0,
                tests_failed=0,
                tests_skipped=0,
                duration_ms=0,
                output=str(e),
                failures=[{"error": str(e)}],
            )

    def _parse_test_output(self, output: str, framework: str) -> Dict[str, Any]:
        """Parse test output to extract metrics."""
        result = {
            "tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "tests_skipped": 0,
            "failures": [],
            "coverage": None,
        }

        import re

        if framework == "pytest":
            # Parse pytest output
            # Format: "5 passed, 2 failed, 1 skipped"
            match = re.search(r'(\d+) passed', output)
            if match:
                result["tests_passed"] = int(match.group(1))

            match = re.search(r'(\d+) failed', output)
            if match:
                result["tests_failed"] = int(match.group(1))

            match = re.search(r'(\d+) skipped', output)
            if match:
                result["tests_skipped"] = int(match.group(1))

            result["tests_run"] = result["tests_passed"] + result["tests_failed"] + result["tests_skipped"]

            # Parse failures
            failure_matches = re.findall(r'FAILED (.+?) -', output)
            for match in failure_matches:
                result["failures"].append({"test": match})

            # Parse coverage
            coverage_match = re.search(r'TOTAL\s+\d+\s+\d+\s+(\d+)%', output)
            if coverage_match:
                result["coverage"] = float(coverage_match.group(1))

        elif framework in ["jest", "vitest"]:
            # Parse Jest/Vitest output
            match = re.search(r'Tests:\s+(\d+) passed', output)
            if match:
                result["tests_passed"] = int(match.group(1))

            match = re.search(r'Tests:\s+.*?(\d+) failed', output)
            if match:
                result["tests_failed"] = int(match.group(1))

            match = re.search(r'Tests:\s+.*?(\d+) skipped', output)
            if match:
                result["tests_skipped"] = int(match.group(1))

            result["tests_run"] = result["tests_passed"] + result["tests_failed"] + result["tests_skipped"]

        elif framework == "go":
            # Parse Go test output
            passed = output.count("--- PASS:")
            failed = output.count("--- FAIL:")
            result["tests_passed"] = passed
            result["tests_failed"] = failed
            result["tests_run"] = passed + failed

        return result

    async def generate_tests(
        self,
        file_path: str,
        function_name: str = None
    ) -> Dict[str, Any]:
        """
        Generate tests for a file or function using Claude.

        Args:
            file_path: Path to the file to test
            function_name: Optional specific function to test

        Returns:
            Dictionary with generated test code
        """
        if not self.claude_cli:
            return {
                "success": False,
                "error": "Claude CLI not available for test generation"
            }

        full_path = self.project_path / file_path
        if not full_path.exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}"
            }

        code = full_path.read_text()

        prompt = f"""Generate tests for this code using {self.test_framework.get('name', 'pytest')}.

FILE: {file_path}
{f"FUNCTION: {function_name}" if function_name else ""}

CODE:
```
{code}
```

Generate comprehensive tests that:
1. Test happy path
2. Test edge cases
3. Test error handling
4. Use appropriate mocking

Return ONLY the test code, no explanation:"""

        try:
            process = await asyncio.create_subprocess_exec(
                self.claude_cli,
                "-p", prompt,
                "--output-format", "text",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=60)
            test_code = stdout.decode("utf-8").strip()

            # Clean up markdown if present
            if test_code.startswith("```"):
                lines = test_code.split("\n")
                test_code = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

            # Determine test file path
            if self.test_framework.get("name") == "pytest":
                test_file = self.project_path / "tests" / f"test_{Path(file_path).stem}.py"
            else:
                test_file = self.project_path / "tests" / f"{Path(file_path).stem}.test.{Path(file_path).suffix}"

            return {
                "success": True,
                "test_code": test_code,
                "suggested_path": str(test_file),
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def verify_task_completion(
        self,
        task_id: str,
        files_changed: List[str] = None
    ) -> Dict[str, Any]:
        """
        Verify that a task is complete by running relevant tests.

        This is the main verification hook called before marking a task done.
        """
        result = await self.run_tests(files_changed=files_changed)

        return {
            "task_id": task_id,
            "verified": result.success,
            "tests_passed": result.tests_passed,
            "tests_failed": result.tests_failed,
            "coverage": result.coverage,
            "message": (
                f"All {result.tests_passed} tests passed"
                if result.success
                else f"{result.tests_failed} tests failed"
            ),
            "promise": (
                "<Promise>DONE</Promise>"
                if result.success
                else f"<Promise>BLOCKED: {result.tests_failed} tests failed</Promise>"
            ),
        }


# Singleton
_testing_agent: Optional[TestingAgent] = None


def get_testing_agent(project_path: Path = None) -> TestingAgent:
    """Get the singleton Testing Agent."""
    global _testing_agent
    if _testing_agent is None or project_path:
        _testing_agent = TestingAgent(project_path)
    return _testing_agent


async def run_tests(project_path: Path = None, with_coverage: bool = False) -> TestResult:
    """Convenience function to run tests."""
    agent = get_testing_agent(project_path)
    return await agent.run_tests(with_coverage=with_coverage)


async def verify_task(task_id: str, files_changed: List[str] = None) -> Dict[str, Any]:
    """Convenience function to verify a task completion."""
    agent = get_testing_agent()
    return await agent.verify_task_completion(task_id, files_changed)
