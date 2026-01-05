"""
Query Status Skill

Gets the status of running jobs, pipelines, or workflows.
"""

from typing import Any, Dict, List, Optional
import httpx

from .base_skill import BaseSkill, SkillResult


class QueryStatus(BaseSkill):
    """
    Skill to query the status of running jobs.

    Can query:
    - Pipeline runs
    - Workflow executions
    - Generic job status
    """

    name = "query_status"
    description = "Get the status of a running job, pipeline, or workflow"
    required_permissions = ["status:read"]
    estimated_cost = 0.01

    async def execute(
        self,
        args: Dict[str, Any],
        context: Optional[Any] = None
    ) -> SkillResult:
        """
        Query job status.

        Args:
            args:
                - job_id: ID of the job to query
                - job_type: Type (pipeline, workflow, generic)
                - include_logs: Whether to include recent logs
        """
        await self.pre_execute(args)

        job_id = args.get("job_id")
        job_type = args.get("job_type", "generic")
        include_logs = args.get("include_logs", False)

        try:
            if job_type == "pipeline":
                status = await self._query_pipeline(job_id)
            elif job_type == "workflow":
                status = await self._query_workflow(job_id)
            else:
                status = await self._query_generic(job_id)

            if include_logs:
                status["recent_logs"] = await self._get_recent_logs(job_id, job_type)

            skill_result = SkillResult(
                success=True,
                data=status,
                cost=self.estimated_cost,
            )

        except Exception as e:
            skill_result = SkillResult(
                success=False,
                error=str(e),
            )

        await self.post_execute(skill_result)
        return skill_result

    async def _query_pipeline(self, job_id: str) -> Dict[str, Any]:
        """Query pipeline status."""
        # Placeholder - would query actual CI/CD system
        return {
            "job_id": job_id,
            "type": "pipeline",
            "status": "running",
            "progress": 50,
            "started_at": "2024-01-01T00:00:00Z",
            "current_step": "build",
            "total_steps": 4,
        }

    async def _query_workflow(self, job_id: str) -> Dict[str, Any]:
        """Query workflow status."""
        return {
            "job_id": job_id,
            "type": "workflow",
            "status": "running",
            "progress": 75,
            "started_at": "2024-01-01T00:00:00Z",
            "current_node": "process_data",
        }

    async def _query_generic(self, job_id: str) -> Dict[str, Any]:
        """Query generic job status."""
        return {
            "job_id": job_id,
            "type": "generic",
            "status": "running",
            "progress": 0,
        }

    async def _get_recent_logs(
        self,
        job_id: str,
        job_type: str
    ) -> List[str]:
        """Get recent logs for a job."""
        return [
            f"[INFO] Job {job_id} started",
            f"[INFO] Processing step 1",
            f"[INFO] Processing step 2",
        ]

    def validate_args(self, args: Dict[str, Any]) -> List[str]:
        errors = []
        if not args.get("job_id"):
            errors.append("job_id is required")
        return errors

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "ID of the job to query",
                },
                "job_type": {
                    "type": "string",
                    "enum": ["pipeline", "workflow", "generic"],
                    "description": "Type of job",
                },
                "include_logs": {
                    "type": "boolean",
                    "description": "Include recent logs in response",
                },
            },
            "required": ["job_id"],
        }
