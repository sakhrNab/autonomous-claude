"""
Base Skill class for all skills.

Skills are ATOMIC - they do ONE thing and return.
Skills do NOT:
- Plan
- Loop
- Make decisions about continuation

Skills DO:
- Take arguments
- Perform one action
- Return structured results
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class SkillResult:
    """Result from a skill execution."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    artifacts: List[str] = field(default_factory=list)
    cost: float = 0.0
    duration_ms: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "artifacts": self.artifacts,
            "cost": self.cost,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }


class BaseSkill(ABC):
    """
    Base class for all skills.

    Skills are atomic units of work. They:
    - Accept specific arguments
    - Perform a single operation
    - Return a structured result

    Skills NEVER make decisions about termination or continuation.
    """

    name: str = "BaseSkill"
    description: str = "Base skill class"
    required_permissions: List[str] = []
    estimated_cost: float = 0.0

    def __init__(self):
        self.execution_count = 0
        self.total_cost = 0.0
        self.last_execution = None

    @abstractmethod
    async def execute(
        self,
        args: Dict[str, Any],
        context: Optional[Any] = None
    ) -> SkillResult:
        """
        Execute the skill.

        Args:
            args: Skill-specific arguments
            context: Optional execution context

        Returns:
            SkillResult with outcome
        """
        pass

    def validate_args(self, args: Dict[str, Any]) -> List[str]:
        """
        Validate arguments before execution.

        Override in subclasses for specific validation.

        Returns:
            List of validation errors (empty if valid)
        """
        return []

    def get_schema(self) -> Dict[str, Any]:
        """Return JSON schema for this skill's arguments."""
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    async def pre_execute(self, args: Dict[str, Any]):
        """Hook called before execution. Override if needed."""
        pass

    async def post_execute(self, result: SkillResult):
        """Hook called after execution. Override if needed."""
        self.execution_count += 1
        self.total_cost += result.cost
        self.last_execution = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert skill info to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "required_permissions": self.required_permissions,
            "estimated_cost": self.estimated_cost,
            "execution_count": self.execution_count,
            "total_cost": self.total_cost,
        }
