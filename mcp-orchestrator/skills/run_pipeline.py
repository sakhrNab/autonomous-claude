"""
Run Pipeline Skill

Triggers CI/CD pipelines or cloud code execution.
"""

from typing import Any, Dict, List, Optional
import asyncio
import httpx

from .base_skill import BaseSkill, SkillResult


class RunPipeline(BaseSkill):
    """
    Skill to trigger and run CI/CD pipelines.

    Supports:
    - GitHub Actions
    - GitLab CI
    - Jenkins
    - Generic webhook-based triggers
    """

    name = "run_pipeline"
    description = "Trigger a CI/CD pipeline or cloud code execution"
    required_permissions = ["pipeline:execute"]
    estimated_cost = 0.10

    def __init__(self, webhook_url: Optional[str] = None):
        super().__init__()
        self.webhook_url = webhook_url

    async def execute(
        self,
        args: Dict[str, Any],
        context: Optional[Any] = None
    ) -> SkillResult:
        """
        Execute a pipeline.

        Args:
            args:
                - pipeline_name: Name/ID of the pipeline
                - type: Type of pipeline (github, gitlab, jenkins, webhook)
                - parameters: Pipeline parameters
                - wait: Whether to wait for completion
        """
        await self.pre_execute(args)

        pipeline_name = args.get("pipeline_name", "default")
        pipeline_type = args.get("type", "webhook")
        parameters = args.get("parameters", {})
        wait = args.get("wait", False)

        try:
            if pipeline_type == "github":
                result = await self._trigger_github(pipeline_name, parameters)
            elif pipeline_type == "gitlab":
                result = await self._trigger_gitlab(pipeline_name, parameters)
            elif pipeline_type == "jenkins":
                result = await self._trigger_jenkins(pipeline_name, parameters)
            else:
                result = await self._trigger_webhook(pipeline_name, parameters)

            skill_result = SkillResult(
                success=True,
                data={
                    "pipeline_name": pipeline_name,
                    "run_id": result.get("run_id"),
                    "status": "triggered",
                    "url": result.get("url"),
                },
                cost=self.estimated_cost,
            )

        except Exception as e:
            skill_result = SkillResult(
                success=False,
                error=str(e),
                cost=0.0,
            )

        await self.post_execute(skill_result)
        return skill_result

    async def _trigger_github(
        self,
        pipeline_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Trigger a GitHub Actions workflow."""
        # In production, use GitHub API
        return {
            "run_id": f"gh-{pipeline_name}-001",
            "url": f"https://github.com/actions/runs/{pipeline_name}",
        }

    async def _trigger_gitlab(
        self,
        pipeline_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Trigger a GitLab CI pipeline."""
        return {
            "run_id": f"gl-{pipeline_name}-001",
            "url": f"https://gitlab.com/pipelines/{pipeline_name}",
        }

    async def _trigger_jenkins(
        self,
        pipeline_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Trigger a Jenkins job."""
        return {
            "run_id": f"jk-{pipeline_name}-001",
            "url": f"https://jenkins.local/job/{pipeline_name}",
        }

    async def _trigger_webhook(
        self,
        pipeline_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Trigger via generic webhook."""
        if not self.webhook_url:
            raise ValueError("No webhook URL configured")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.webhook_url,
                json={
                    "pipeline": pipeline_name,
                    "parameters": parameters,
                },
                timeout=30.0,
            )
            response.raise_for_status()

            return response.json()

    def validate_args(self, args: Dict[str, Any]) -> List[str]:
        errors = []
        if not args.get("pipeline_name"):
            errors.append("pipeline_name is required")
        return errors

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pipeline_name": {
                    "type": "string",
                    "description": "Name or ID of the pipeline to run",
                },
                "type": {
                    "type": "string",
                    "enum": ["github", "gitlab", "jenkins", "webhook"],
                    "description": "Type of pipeline system",
                },
                "parameters": {
                    "type": "object",
                    "description": "Pipeline parameters",
                },
                "wait": {
                    "type": "boolean",
                    "description": "Wait for pipeline completion",
                },
            },
            "required": ["pipeline_name"],
        }
