"""
Route Message Skill

Determines which MCP, workflow, skill, or hook to call for each message.

Per SESSION 2 Guide:
- For each message, correct remote MCP or workflow is triggered automatically
- Decision Agent works with this skill to dynamically select routes
"""

from typing import Any, Dict, List, Optional

from .base_skill import BaseSkill, SkillResult


class RouteMessage(BaseSkill):
    """
    Route Message Skill - Determines routing for messages.

    This skill:
    - Analyzes message content
    - Determines the best route (MCP, workflow, skill, hook)
    - Returns routing decision with confidence
    """

    name = "route_message"
    description = "Route a message to the appropriate MCP, workflow, skill, or hook"
    required_permissions = ["message:route"]
    estimated_cost = 0.0

    def __init__(self):
        super().__init__()

        # Routing rules
        self.mcp_routes = {
            "database": ["query", "select", "insert", "update", "delete", "sql"],
            "file": ["read", "write", "upload", "download", "file", "document"],
            "api": ["request", "fetch", "call", "endpoint", "rest", "graphql"],
            "auth": ["login", "logout", "authenticate", "authorize", "permission"],
            "notification": ["notify", "alert", "message", "email", "slack"],
        }

        self.workflow_routes = {
            "deploy": ["deploy", "release", "publish", "rollout"],
            "build": ["build", "compile", "package", "bundle"],
            "test": ["test", "verify", "validate", "check"],
            "data_pipeline": ["etl", "transform", "load", "sync", "migrate"],
            "report": ["report", "analyze", "metrics", "dashboard"],
        }

        self.skill_routes = {
            "run_pipeline": ["pipeline", "ci", "cd"],
            "run_workflow": ["workflow", "automation", "n8n"],
            "query_status": ["status", "progress", "state"],
            "fetch_logs": ["logs", "trace", "debug"],
            "apply_fix": ["fix", "repair", "patch"],
            "send_notification": ["notify", "alert"],
        }

    async def execute(
        self,
        args: Dict[str, Any],
        context: Optional[Any] = None
    ) -> SkillResult:
        """
        Route a message to the appropriate destination.

        Args:
            args:
                - content: Message content
                - message_id: Message ID
                - session_id: Session ID
                - force_route: Optional forced route
        """
        await self.pre_execute(args)

        content = args.get("content", "").lower()
        message_id = args.get("message_id")
        session_id = args.get("session_id")
        force_route = args.get("force_route")

        if force_route:
            result = self._create_forced_route(force_route, args)
        else:
            result = self._determine_route(content)

        result["message_id"] = message_id
        result["session_id"] = session_id

        skill_result = SkillResult(
            success=True,
            data=result,
            cost=0.0,
        )

        await self.post_execute(skill_result)
        return skill_result

    def _determine_route(self, content: str) -> Dict[str, Any]:
        """Determine the best route for the content."""
        routes = []

        # Check MCP routes
        for mcp, keywords in self.mcp_routes.items():
            score = sum(1 for kw in keywords if kw in content)
            if score > 0:
                routes.append({
                    "type": "mcp",
                    "name": mcp,
                    "score": score / len(keywords),
                    "keywords_matched": [kw for kw in keywords if kw in content],
                })

        # Check workflow routes
        for workflow, keywords in self.workflow_routes.items():
            score = sum(1 for kw in keywords if kw in content)
            if score > 0:
                routes.append({
                    "type": "workflow",
                    "name": workflow,
                    "score": score / len(keywords),
                    "keywords_matched": [kw for kw in keywords if kw in content],
                })

        # Check skill routes
        for skill, keywords in self.skill_routes.items():
            score = sum(1 for kw in keywords if kw in content)
            if score > 0:
                routes.append({
                    "type": "skill",
                    "name": skill,
                    "score": score / len(keywords),
                    "keywords_matched": [kw for kw in keywords if kw in content],
                })

        # Sort by score
        routes.sort(key=lambda r: r["score"], reverse=True)

        if routes:
            best = routes[0]
            return {
                "route_type": best["type"],
                "route_name": best["name"],
                "confidence": min(best["score"] + 0.3, 1.0),
                "keywords_matched": best["keywords_matched"],
                "alternatives": routes[1:4],
            }

        # Default route
        return {
            "route_type": "agent",
            "route_name": "planner",
            "confidence": 0.5,
            "reason": "No specific route matched, defaulting to planner",
            "alternatives": [],
        }

    def _create_forced_route(
        self,
        force_route: Dict[str, Any],
        args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a forced routing decision."""
        return {
            "route_type": force_route.get("type", "skill"),
            "route_name": force_route.get("name", "unknown"),
            "confidence": 1.0,
            "forced": True,
            "original_args": args,
        }

    def validate_args(self, args: Dict[str, Any]) -> List[str]:
        errors = []
        if not args.get("content") and not args.get("force_route"):
            errors.append("content or force_route is required")
        return errors

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Message content to route",
                },
                "message_id": {
                    "type": "string",
                    "description": "Message ID",
                },
                "session_id": {
                    "type": "string",
                    "description": "Session ID",
                },
                "force_route": {
                    "type": "object",
                    "description": "Force a specific route",
                    "properties": {
                        "type": {"type": "string"},
                        "name": {"type": "string"},
                    },
                },
            },
        }

    def add_mcp_route(self, mcp_name: str, keywords: List[str]):
        """Add a new MCP route."""
        self.mcp_routes[mcp_name] = keywords

    def add_workflow_route(self, workflow_name: str, keywords: List[str]):
        """Add a new workflow route."""
        self.workflow_routes[workflow_name] = keywords

    def add_skill_route(self, skill_name: str, keywords: List[str]):
        """Add a new skill route."""
        self.skill_routes[skill_name] = keywords

    def get_available_routes(self) -> Dict[str, List[str]]:
        """Get all available routes."""
        return {
            "mcps": list(self.mcp_routes.keys()),
            "workflows": list(self.workflow_routes.keys()),
            "skills": list(self.skill_routes.keys()),
        }
