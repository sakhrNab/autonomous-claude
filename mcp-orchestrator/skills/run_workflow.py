"""
Run Workflow Skill

Triggers workflow engines like n8n, Temporal, or Prefect.
"""

from typing import Any, Dict, List, Optional
import httpx

from .base_skill import BaseSkill, SkillResult


class RunWorkflow(BaseSkill):
    """
    Skill to trigger workflow orchestration systems.

    Supports:
    - n8n
    - Temporal
    - Prefect
    - Generic HTTP triggers
    """

    name = "run_workflow"
    description = "Trigger a workflow in n8n, Temporal, or similar systems"
    required_permissions = ["workflow:execute"]
    estimated_cost = 0.05

    def __init__(
        self,
        n8n_url: Optional[str] = None,
        n8n_api_key: Optional[str] = None
    ):
        super().__init__()
        self.n8n_url = n8n_url
        self.n8n_api_key = n8n_api_key

    async def execute(
        self,
        args: Dict[str, Any],
        context: Optional[Any] = None
    ) -> SkillResult:
        """
        Execute a workflow.

        Args:
            args:
                - workflow_name: Name/ID of the workflow
                - workflow_type: Type (n8n, temporal, prefect, http)
                - input_data: Data to pass to the workflow
                - wait: Whether to wait for completion
        """
        await self.pre_execute(args)

        workflow_name = args.get("workflow_name", "default")
        workflow_type = args.get("workflow_type", "n8n")
        input_data = args.get("input_data", {})
        wait = args.get("wait", False)

        try:
            if workflow_type == "n8n":
                result = await self._trigger_n8n(workflow_name, input_data)
            elif workflow_type == "temporal":
                result = await self._trigger_temporal(workflow_name, input_data)
            elif workflow_type == "prefect":
                result = await self._trigger_prefect(workflow_name, input_data)
            else:
                result = await self._trigger_http(workflow_name, input_data)

            skill_result = SkillResult(
                success=True,
                data={
                    "workflow_name": workflow_name,
                    "execution_id": result.get("execution_id"),
                    "status": "triggered",
                },
                cost=self.estimated_cost,
            )

        except Exception as e:
            skill_result = SkillResult(
                success=False,
                error=str(e),
            )

        await self.post_execute(skill_result)
        return skill_result

    async def _trigger_n8n(
        self,
        workflow_name: str,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Trigger an n8n workflow via webhook."""
        if not self.n8n_url:
            raise ValueError("n8n URL not configured")

        headers = {}
        if self.n8n_api_key:
            headers["X-N8N-API-KEY"] = self.n8n_api_key

        async with httpx.AsyncClient() as client:
            # n8n webhook URL format
            url = f"{self.n8n_url}/webhook/{workflow_name}"

            response = await client.post(
                url,
                json=input_data,
                headers=headers,
                timeout=60.0,
            )
            response.raise_for_status()

            return {
                "execution_id": f"n8n-{workflow_name}-001",
                "response": response.json() if response.content else {},
            }

    async def _trigger_temporal(
        self,
        workflow_name: str,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Trigger a Temporal workflow."""
        # Placeholder for Temporal SDK integration
        return {
            "execution_id": f"temporal-{workflow_name}-001",
        }

    async def _trigger_prefect(
        self,
        workflow_name: str,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Trigger a Prefect flow."""
        # Placeholder for Prefect API integration
        return {
            "execution_id": f"prefect-{workflow_name}-001",
        }

    async def _trigger_http(
        self,
        workflow_name: str,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Trigger via generic HTTP endpoint."""
        url = input_data.get("url") or workflow_name

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=input_data.get("payload", {}),
                timeout=60.0,
            )
            response.raise_for_status()

            return {
                "execution_id": f"http-{workflow_name}-001",
                "response": response.json() if response.content else {},
            }

    def validate_args(self, args: Dict[str, Any]) -> List[str]:
        errors = []
        if not args.get("workflow_name"):
            errors.append("workflow_name is required")
        return errors

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workflow_name": {
                    "type": "string",
                    "description": "Name or ID of the workflow",
                },
                "workflow_type": {
                    "type": "string",
                    "enum": ["n8n", "temporal", "prefect", "http"],
                    "description": "Type of workflow system",
                },
                "input_data": {
                    "type": "object",
                    "description": "Input data for the workflow",
                },
                "wait": {
                    "type": "boolean",
                    "description": "Wait for workflow completion",
                },
            },
            "required": ["workflow_name"],
        }
