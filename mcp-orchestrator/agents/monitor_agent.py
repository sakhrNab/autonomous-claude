"""
Monitor Agent

RESPONSIBILITY: Observe long-running jobs.

This agent:
- Checks job statuses
- Detects anomalies
- Reports progress
- Triggers alerts on issues

Used for:
- Pipelines
- Scheduled workflows
- Async jobs
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import asyncio

from .base_agent import BaseAgent, AgentContext, AgentResult


class MonitorAgent(BaseAgent):
    """
    Monitor Agent - Observes and reports on long-running jobs.

    This agent watches jobs and reports their status.
    It does not take corrective action - that's the Debugger's job.
    """

    def __init__(self):
        super().__init__(name="MonitorAgent")
        self.watched_jobs: Dict[str, Dict[str, Any]] = {}
        self.polling_interval: int = 10  # seconds
        self.max_watch_time: int = 3600  # 1 hour

    async def perform_step(self, context: AgentContext) -> AgentResult:
        """
        Monitor jobs and report status.
        """
        self.iteration_count += 1

        action = context.plan.get("action", "check_status") if context.plan else "check_status"

        if action == "watch_job":
            return await self._start_watching(context)
        elif action == "check_status":
            return await self._check_all_jobs(context)
        elif action == "stop_watching":
            return await self._stop_watching(context)
        elif action == "detect_anomalies":
            return await self._detect_anomalies(context)
        else:
            return AgentResult(
                success=False,
                error=f"Unknown action: {action}",
            )

    async def _start_watching(self, context: AgentContext) -> AgentResult:
        """Start watching a new job."""
        job_id = context.plan.get("job_id") if context.plan else None
        job_type = context.plan.get("job_type", "unknown") if context.plan else "unknown"

        if not job_id:
            return AgentResult(
                success=False,
                error="No job_id provided",
            )

        self.watched_jobs[job_id] = {
            "job_id": job_id,
            "job_type": job_type,
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "last_checked": None,
            "progress": 0,
            "logs": [],
        }

        self.log("info", f"Started watching job", {"job_id": job_id})

        return AgentResult(
            success=True,
            data={"job_id": job_id, "watching": True},
        )

    async def _check_all_jobs(self, context: AgentContext) -> AgentResult:
        """Check status of all watched jobs."""
        results = []

        for job_id, job_info in self.watched_jobs.items():
            status = await self._get_job_status(job_id, job_info)
            job_info["status"] = status["status"]
            job_info["progress"] = status.get("progress", 0)
            job_info["last_checked"] = datetime.now().isoformat()

            results.append({
                "job_id": job_id,
                "status": status["status"],
                "progress": status.get("progress", 0),
            })

            # Log status changes
            self.log("info", f"Job status", {
                "job_id": job_id,
                "status": status["status"],
            })

        # Determine overall status
        all_complete = all(r["status"] == "completed" for r in results)
        any_failed = any(r["status"] == "failed" for r in results)

        return AgentResult(
            success=not any_failed,
            data={
                "jobs": results,
                "all_complete": all_complete,
                "any_failed": any_failed,
            },
        )

    async def _get_job_status(self, job_id: str, job_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get the current status of a job.

        In production, this would call the actual job API.
        """
        # Simulate status check
        # In real implementation, this would query the actual job system
        job_type = job_info.get("job_type", "unknown")

        # Placeholder for actual API call
        status = {
            "status": "running",
            "progress": 50,
            "message": "Job in progress",
        }

        return status

    async def _stop_watching(self, context: AgentContext) -> AgentResult:
        """Stop watching a job."""
        job_id = context.plan.get("job_id") if context.plan else None

        if job_id and job_id in self.watched_jobs:
            del self.watched_jobs[job_id]
            return AgentResult(
                success=True,
                data={"job_id": job_id, "stopped": True},
            )

        return AgentResult(
            success=False,
            error=f"Job not found: {job_id}",
        )

    async def _detect_anomalies(self, context: AgentContext) -> AgentResult:
        """
        Detect anomalies in job execution.

        Looks for:
        - Jobs running too long
        - Jobs with no progress
        - Unexpected status changes
        """
        anomalies = []

        for job_id, job_info in self.watched_jobs.items():
            # Check for long-running jobs
            started = datetime.fromisoformat(job_info["started_at"])
            elapsed = (datetime.now() - started).total_seconds()

            if elapsed > self.max_watch_time:
                anomalies.append({
                    "job_id": job_id,
                    "type": "long_running",
                    "message": f"Job running for {elapsed/60:.1f} minutes",
                })

            # Check for stalled jobs
            if job_info.get("progress", 0) == 0 and elapsed > 300:
                anomalies.append({
                    "job_id": job_id,
                    "type": "no_progress",
                    "message": "Job has no progress after 5 minutes",
                })

        if anomalies:
            self.log("warning", "Anomalies detected", {
                "count": len(anomalies),
            })

        return AgentResult(
            success=len(anomalies) == 0,
            data={
                "anomalies": anomalies,
                "anomaly_count": len(anomalies),
            },
        )

    async def poll_until_complete(
        self,
        job_id: str,
        timeout_seconds: int = 3600
    ) -> AgentResult:
        """
        Poll a job until it completes or times out.
        """
        start_time = datetime.now()
        last_status = None

        while True:
            elapsed = (datetime.now() - start_time).total_seconds()

            if elapsed > timeout_seconds:
                return AgentResult(
                    success=False,
                    error=f"Timeout waiting for job {job_id}",
                    data={"elapsed_seconds": elapsed},
                )

            if job_id in self.watched_jobs:
                job_info = self.watched_jobs[job_id]
                status = await self._get_job_status(job_id, job_info)

                if status["status"] != last_status:
                    self.log("info", f"Job status changed", {
                        "job_id": job_id,
                        "from": last_status,
                        "to": status["status"],
                    })
                    last_status = status["status"]

                if status["status"] == "completed":
                    return AgentResult(
                        success=True,
                        data={"job_id": job_id, "status": "completed"},
                    )
                elif status["status"] == "failed":
                    return AgentResult(
                        success=False,
                        error=f"Job {job_id} failed",
                        data={"job_id": job_id, "status": "failed"},
                    )

            await asyncio.sleep(self.polling_interval)
