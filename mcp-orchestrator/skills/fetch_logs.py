"""
Fetch Logs Skill

Retrieves logs and artifacts from jobs.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import httpx

from .base_skill import BaseSkill, SkillResult


class FetchLogs(BaseSkill):
    """
    Skill to fetch logs and artifacts.

    Can retrieve:
    - Execution logs
    - Error traces
    - Artifacts (files, reports)
    """

    name = "fetch_logs"
    description = "Retrieve logs and artifacts from job executions"
    required_permissions = ["logs:read"]
    estimated_cost = 0.02

    async def execute(
        self,
        args: Dict[str, Any],
        context: Optional[Any] = None
    ) -> SkillResult:
        """
        Fetch logs.

        Args:
            args:
                - job_id: ID of the job
                - log_type: Type (stdout, stderr, all)
                - lines: Number of lines to fetch
                - since: Timestamp to fetch logs from
                - include_artifacts: Include artifact list
        """
        await self.pre_execute(args)

        job_id = args.get("job_id")
        log_type = args.get("log_type", "all")
        lines = args.get("lines", 100)
        since = args.get("since")
        include_artifacts = args.get("include_artifacts", False)

        try:
            logs = await self._fetch_logs(job_id, log_type, lines, since)

            data = {
                "job_id": job_id,
                "log_type": log_type,
                "logs": logs,
                "line_count": len(logs),
            }

            if include_artifacts:
                data["artifacts"] = await self._list_artifacts(job_id)

            skill_result = SkillResult(
                success=True,
                data=data,
                artifacts=data.get("artifacts", []),
                cost=self.estimated_cost,
            )

        except Exception as e:
            skill_result = SkillResult(
                success=False,
                error=str(e),
            )

        await self.post_execute(skill_result)
        return skill_result

    async def _fetch_logs(
        self,
        job_id: str,
        log_type: str,
        lines: int,
        since: Optional[str]
    ) -> List[str]:
        """Fetch logs from storage."""
        # Placeholder - would fetch from actual log storage
        sample_logs = [
            f"{datetime.now().isoformat()} [INFO] Starting job {job_id}",
            f"{datetime.now().isoformat()} [INFO] Initializing environment",
            f"{datetime.now().isoformat()} [INFO] Running main process",
            f"{datetime.now().isoformat()} [DEBUG] Processing data chunk 1",
            f"{datetime.now().isoformat()} [DEBUG] Processing data chunk 2",
        ]

        if log_type == "stderr":
            sample_logs = [
                f"{datetime.now().isoformat()} [ERROR] Connection failed",
                f"{datetime.now().isoformat()} [WARN] Retrying operation",
            ]

        return sample_logs[:lines]

    async def _list_artifacts(self, job_id: str) -> List[str]:
        """List artifacts for a job."""
        return [
            f"artifacts/{job_id}/output.json",
            f"artifacts/{job_id}/report.html",
            f"artifacts/{job_id}/logs.tar.gz",
        ]

    def validate_args(self, args: Dict[str, Any]) -> List[str]:
        errors = []
        if not args.get("job_id"):
            errors.append("job_id is required")
        lines = args.get("lines", 100)
        if lines > 10000:
            errors.append("lines cannot exceed 10000")
        return errors

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "ID of the job",
                },
                "log_type": {
                    "type": "string",
                    "enum": ["stdout", "stderr", "all"],
                    "description": "Type of logs to fetch",
                },
                "lines": {
                    "type": "integer",
                    "description": "Number of lines to fetch",
                    "default": 100,
                },
                "since": {
                    "type": "string",
                    "description": "ISO timestamp to fetch logs from",
                },
                "include_artifacts": {
                    "type": "boolean",
                    "description": "Include artifact list",
                },
            },
            "required": ["job_id"],
        }
