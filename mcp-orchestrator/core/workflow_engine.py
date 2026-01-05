"""
Workflow Engine

Handles the end-to-end workflow from voice input to result delivery.

Flow (per guides):
1) User sends voice/text message
2) speech_to_text skill converts it (if voice)
3) Planner Agent creates plan
4) MCP Orchestrator spawns subagents
5) Executor Agent runs skills
6) Post-step hook runs tests
7) Stop hook evaluates state
8) text_to_speech generates voice summary
9) UI shows timeline + results
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import asyncio

from .orchestrator import MCPOrchestrator
from .config import Config


class WorkflowEngine:
    """
    Workflow Engine - High-level workflow coordination.

    This engine provides a clean interface for:
    - Voice-first interactions
    - Text-based interactions
    - Workflow monitoring
    - Result delivery
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.orchestrator = MCPOrchestrator(config)
        self.active_workflows: Dict[str, Dict[str, Any]] = {}

    async def process_voice_input(
        self,
        user_id: str,
        audio_data: bytes,
        audio_format: str = "wav"
    ) -> Dict[str, Any]:
        """
        Process voice input through the full workflow.

        Steps:
        1) Convert speech to text
        2) Execute workflow
        3) Generate voice response
        """
        from ..skills import SpeechToText, TextToSpeech

        # Step 1: Convert speech to text
        stt = SpeechToText(provider="openai", api_key=self.config.integrations.openai_api_key)
        stt_result = await stt.execute({
            "audio_data": audio_data.decode() if isinstance(audio_data, bytes) else audio_data,
        })

        if not stt_result.success:
            return {
                "success": False,
                "error": f"Speech recognition failed: {stt_result.error}",
            }

        intent = stt_result.data.get("transcript", "")

        # Step 2: Execute the workflow
        result = await self.execute_workflow(user_id, intent)

        # Step 3: Generate voice response
        if result.get("success"):
            tts = TextToSpeech(provider="openai", api_key=self.config.integrations.openai_api_key)

            summary = self._generate_summary(result)
            tts_result = await tts.execute({"text": summary})

            result["voice_response"] = {
                "text": summary,
                "audio_data": tts_result.data.get("audio_data") if tts_result.success else None,
            }

        return result

    async def process_text_input(
        self,
        user_id: str,
        text: str
    ) -> Dict[str, Any]:
        """
        Process text input through the workflow.
        """
        return await self.execute_workflow(user_id, text)

    async def execute_workflow(
        self,
        user_id: str,
        intent: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute the main workflow.

        This is the core entry point that:
        - Delegates to the orchestrator
        - Tracks active workflows
        - Handles errors gracefully
        """
        options = options or {}

        workflow_id = f"wf_{datetime.now().strftime('%Y%m%d%H%M%S')}_{user_id[:8]}"

        self.active_workflows[workflow_id] = {
            "workflow_id": workflow_id,
            "user_id": user_id,
            "intent": intent,
            "started_at": datetime.now().isoformat(),
            "status": "running",
        }

        try:
            result = await self.orchestrator.execute(
                user_id=user_id,
                intent=intent,
                budget_limit=options.get("budget_limit"),
            )

            self.active_workflows[workflow_id]["status"] = "completed"
            self.active_workflows[workflow_id]["result"] = result
            self.active_workflows[workflow_id]["completed_at"] = datetime.now().isoformat()

            return {
                "success": result.get("success", False),
                "workflow_id": workflow_id,
                "session_id": result.get("session_id"),
                "result": result.get("result"),
                "error": result.get("error"),
            }

        except Exception as e:
            self.active_workflows[workflow_id]["status"] = "failed"
            self.active_workflows[workflow_id]["error"] = str(e)

            return {
                "success": False,
                "workflow_id": workflow_id,
                "error": str(e),
            }

    async def get_workflow_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a workflow."""
        workflow = self.active_workflows.get(workflow_id)
        if not workflow:
            return None

        # Get session status if available
        session_id = workflow.get("result", {}).get("session_id")
        session_status = None
        if session_id:
            session_status = await self.orchestrator.get_session_status(session_id)

        return {
            **workflow,
            "session_status": session_status,
        }

    async def get_active_workflows(self) -> List[Dict[str, Any]]:
        """Get all active workflows."""
        return [
            w for w in self.active_workflows.values()
            if w.get("status") == "running"
        ]

    async def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel a running workflow."""
        workflow = self.active_workflows.get(workflow_id)
        if not workflow or workflow.get("status") != "running":
            return False

        session_id = workflow.get("result", {}).get("session_id")
        if session_id:
            await self.orchestrator.terminate_session(session_id)

        workflow["status"] = "cancelled"
        workflow["cancelled_at"] = datetime.now().isoformat()

        return True

    def _generate_summary(self, result: Dict[str, Any]) -> str:
        """Generate a voice-friendly summary of the result."""
        if not result.get("success"):
            return f"The workflow failed. {result.get('error', 'Unknown error')}"

        workflow_result = result.get("result", {})
        iterations = workflow_result.get("iterations", 0)
        elapsed = workflow_result.get("elapsed_seconds", 0)
        budget = workflow_result.get("budget_spent", 0)

        summary_parts = ["Workflow completed successfully."]

        if iterations > 0:
            summary_parts.append(f"Completed in {iterations} iterations.")

        if elapsed > 0:
            if elapsed < 60:
                summary_parts.append(f"Total time: {elapsed:.1f} seconds.")
            else:
                minutes = elapsed / 60
                summary_parts.append(f"Total time: {minutes:.1f} minutes.")

        if budget > 0:
            summary_parts.append(f"Cost: ${budget:.2f}.")

        return " ".join(summary_parts)


class WorkflowBuilder:
    """
    Builder for creating custom workflows.

    Allows programmatic construction of multi-step workflows.
    """

    def __init__(self):
        self.steps: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {}

    def add_step(
        self,
        agent: str,
        skill: str,
        args: Optional[Dict[str, Any]] = None,
        description: str = "",
        requires_approval: bool = False
    ) -> "WorkflowBuilder":
        """Add a step to the workflow."""
        self.steps.append({
            "agent": agent,
            "skill": skill,
            "args": args or {},
            "description": description or f"{agent}:{skill}",
            "requires_approval": requires_approval,
        })
        return self

    def set_metadata(self, key: str, value: Any) -> "WorkflowBuilder":
        """Set workflow metadata."""
        self.metadata[key] = value
        return self

    def build(self) -> Dict[str, Any]:
        """Build the workflow definition."""
        return {
            "steps": self.steps,
            "metadata": self.metadata,
            "created_at": datetime.now().isoformat(),
        }

    # Convenience methods for common patterns

    def add_pipeline_step(self, pipeline_name: str, wait: bool = True) -> "WorkflowBuilder":
        """Add a pipeline execution step."""
        return self.add_step(
            "executor",
            "run_pipeline",
            {"pipeline_name": pipeline_name, "wait": wait},
            f"Run pipeline: {pipeline_name}",
        )

    def add_workflow_step(self, workflow_name: str) -> "WorkflowBuilder":
        """Add a workflow execution step."""
        return self.add_step(
            "executor",
            "run_workflow",
            {"workflow_name": workflow_name},
            f"Run workflow: {workflow_name}",
        )

    def add_monitoring_step(self, job_id: str) -> "WorkflowBuilder":
        """Add a monitoring step."""
        return self.add_step(
            "monitor",
            "query_status",
            {"job_id": job_id},
            f"Monitor: {job_id}",
        )

    def add_notification_step(
        self,
        message: str,
        channel: str = "slack"
    ) -> "WorkflowBuilder":
        """Add a notification step."""
        return self.add_step(
            "executor",
            "send_notification",
            {"message": message, "channel": channel},
            "Send notification",
        )

    def add_debug_step(self) -> "WorkflowBuilder":
        """Add a debugging step."""
        return self.add_step(
            "debugger",
            "fetch_logs",
            {},
            "Analyze and debug",
        )
