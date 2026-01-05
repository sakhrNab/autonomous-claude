"""
Cloud Code Adapter

Handles remote Cloud Code triggers, passes message/task context, receives results.

Per SESSION 2 Guide:
- Cloud Code runs REMOTELY, fully autonomously
- For each message, correct remote MCP or workflow is triggered automatically
- Results returned, task ledger updated
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import asyncio
import httpx


class CloudCodeProvider(Enum):
    """Supported Cloud Code providers."""
    GENERIC = "generic"
    AWS_LAMBDA = "aws_lambda"
    GOOGLE_CLOUD_FUNCTIONS = "google_cloud_functions"
    AZURE_FUNCTIONS = "azure_functions"
    CLOUDFLARE_WORKERS = "cloudflare_workers"
    N8N = "n8n"
    TEMPORAL = "temporal"


@dataclass
class CloudCodeRequest:
    """A request to Cloud Code."""
    request_id: str
    provider: CloudCodeProvider
    endpoint: str
    method: str
    payload: Dict[str, Any]
    headers: Dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 60
    retry_count: int = 0
    max_retries: int = 3

    # Context
    message_id: Optional[str] = None
    task_id: Optional[str] = None
    session_id: Optional[str] = None


@dataclass
class CloudCodeResponse:
    """Response from Cloud Code."""
    request_id: str
    success: bool
    status_code: int
    data: Optional[Dict[str, Any]]
    error: Optional[str] = None
    duration_ms: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


class CloudCodeAdapter:
    """
    Cloud Code Adapter - Interface to remote Cloud Code execution.

    This adapter:
    - Triggers remote Cloud Code (Lambda, Cloud Functions, etc.)
    - Passes message and task context
    - Receives and processes results
    - Handles retries and errors
    - Updates task ledger with results
    """

    def __init__(
        self,
        default_timeout: int = 60,
        max_retries: int = 3
    ):
        self.default_timeout = default_timeout
        self.max_retries = max_retries
        self.endpoints: Dict[str, Dict[str, Any]] = {}
        self.request_history: List[CloudCodeResponse] = []

    def register_endpoint(
        self,
        name: str,
        provider: CloudCodeProvider,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Register a Cloud Code endpoint."""
        self.endpoints[name] = {
            "name": name,
            "provider": provider,
            "url": url,
            "headers": headers or {},
            "metadata": metadata or {},
        }

    async def execute(
        self,
        endpoint_name: str,
        payload: Dict[str, Any],
        message_id: Optional[str] = None,
        task_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> CloudCodeResponse:
        """
        Execute Cloud Code at the specified endpoint.

        Per SESSION 2 Guide: Cloud Code runs remotely, fully autonomously.
        """
        endpoint = self.endpoints.get(endpoint_name)
        if not endpoint:
            return CloudCodeResponse(
                request_id="error",
                success=False,
                status_code=404,
                data=None,
                error=f"Endpoint not found: {endpoint_name}",
            )

        import uuid
        request = CloudCodeRequest(
            request_id=str(uuid.uuid4()),
            provider=endpoint["provider"],
            endpoint=endpoint["url"],
            method="POST",
            payload=payload,
            headers=endpoint.get("headers", {}),
            timeout_seconds=self.default_timeout,
            max_retries=self.max_retries,
            message_id=message_id,
            task_id=task_id,
            session_id=session_id,
        )

        # Add context to payload
        request.payload["_context"] = {
            "message_id": message_id,
            "task_id": task_id,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
        }

        return await self._execute_request(request)

    async def _execute_request(self, request: CloudCodeRequest) -> CloudCodeResponse:
        """Execute the actual HTTP request with retry logic."""
        start_time = datetime.now()

        while request.retry_count <= request.max_retries:
            try:
                response = await self._make_http_request(request)

                # Record history
                self.request_history.append(response)

                if response.success:
                    return response

                # Retry on failure if retries remaining
                request.retry_count += 1
                if request.retry_count <= request.max_retries:
                    await asyncio.sleep(2 ** request.retry_count)  # Exponential backoff
                    continue

                return response

            except Exception as e:
                request.retry_count += 1
                if request.retry_count > request.max_retries:
                    duration = int((datetime.now() - start_time).total_seconds() * 1000)
                    return CloudCodeResponse(
                        request_id=request.request_id,
                        success=False,
                        status_code=500,
                        data=None,
                        error=str(e),
                        duration_ms=duration,
                    )

                await asyncio.sleep(2 ** request.retry_count)

        duration = int((datetime.now() - start_time).total_seconds() * 1000)
        return CloudCodeResponse(
            request_id=request.request_id,
            success=False,
            status_code=500,
            data=None,
            error="Max retries exceeded",
            duration_ms=duration,
        )

    async def _make_http_request(self, request: CloudCodeRequest) -> CloudCodeResponse:
        """Make the actual HTTP request."""
        start_time = datetime.now()

        async with httpx.AsyncClient() as client:
            try:
                # Select method based on provider
                if request.provider == CloudCodeProvider.N8N:
                    response = await self._execute_n8n(client, request)
                elif request.provider == CloudCodeProvider.AWS_LAMBDA:
                    response = await self._execute_aws_lambda(client, request)
                elif request.provider == CloudCodeProvider.GOOGLE_CLOUD_FUNCTIONS:
                    response = await self._execute_gcp(client, request)
                else:
                    response = await self._execute_generic(client, request)

                duration = int((datetime.now() - start_time).total_seconds() * 1000)

                return CloudCodeResponse(
                    request_id=request.request_id,
                    success=response.status_code < 400,
                    status_code=response.status_code,
                    data=response.json() if response.content else None,
                    duration_ms=duration,
                )

            except httpx.TimeoutException:
                duration = int((datetime.now() - start_time).total_seconds() * 1000)
                return CloudCodeResponse(
                    request_id=request.request_id,
                    success=False,
                    status_code=408,
                    data=None,
                    error="Request timeout",
                    duration_ms=duration,
                )

    async def _execute_generic(
        self,
        client: httpx.AsyncClient,
        request: CloudCodeRequest
    ) -> httpx.Response:
        """Execute generic HTTP request."""
        return await client.post(
            request.endpoint,
            json=request.payload,
            headers=request.headers,
            timeout=request.timeout_seconds,
        )

    async def _execute_n8n(
        self,
        client: httpx.AsyncClient,
        request: CloudCodeRequest
    ) -> httpx.Response:
        """Execute n8n webhook request."""
        headers = {**request.headers}
        return await client.post(
            request.endpoint,
            json=request.payload,
            headers=headers,
            timeout=request.timeout_seconds,
        )

    async def _execute_aws_lambda(
        self,
        client: httpx.AsyncClient,
        request: CloudCodeRequest
    ) -> httpx.Response:
        """Execute AWS Lambda request."""
        # In production, would use AWS SDK with proper signing
        return await self._execute_generic(client, request)

    async def _execute_gcp(
        self,
        client: httpx.AsyncClient,
        request: CloudCodeRequest
    ) -> httpx.Response:
        """Execute Google Cloud Functions request."""
        # In production, would use GCP SDK with proper auth
        return await self._execute_generic(client, request)

    async def trigger_mcp(
        self,
        mcp_name: str,
        action: str,
        params: Dict[str, Any],
        message_id: Optional[str] = None,
        task_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> CloudCodeResponse:
        """
        Trigger a remote MCP.

        Per SESSION 2 Guide: For each message, correct remote MCP is triggered automatically.
        """
        # Look up MCP endpoint
        endpoint_name = f"mcp_{mcp_name}"

        if endpoint_name not in self.endpoints:
            # Try to auto-discover or use default
            endpoint_name = "default_mcp"

        payload = {
            "mcp": mcp_name,
            "action": action,
            "params": params,
        }

        return await self.execute(
            endpoint_name,
            payload,
            message_id=message_id,
            task_id=task_id,
            session_id=session_id,
        )

    async def trigger_workflow(
        self,
        workflow_name: str,
        input_data: Dict[str, Any],
        message_id: Optional[str] = None,
        task_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> CloudCodeResponse:
        """
        Trigger a remote workflow.

        Per SESSION 2 Guide: Cloud Code runs remotely, fully autonomously.
        """
        endpoint_name = f"workflow_{workflow_name}"

        if endpoint_name not in self.endpoints:
            endpoint_name = "default_workflow"

        payload = {
            "workflow": workflow_name,
            "input": input_data,
        }

        return await self.execute(
            endpoint_name,
            payload,
            message_id=message_id,
            task_id=task_id,
            session_id=session_id,
        )

    def get_request_history(
        self,
        limit: int = 100,
        success_only: bool = False
    ) -> List[CloudCodeResponse]:
        """Get request history."""
        history = self.request_history
        if success_only:
            history = [r for r in history if r.success]
        return history[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Get adapter statistics."""
        total = len(self.request_history)
        successful = len([r for r in self.request_history if r.success])
        avg_duration = (
            sum(r.duration_ms for r in self.request_history) / total
            if total > 0 else 0
        )

        return {
            "total_requests": total,
            "successful_requests": successful,
            "failed_requests": total - successful,
            "success_rate": successful / total if total > 0 else 0,
            "average_duration_ms": avg_duration,
            "registered_endpoints": len(self.endpoints),
        }
