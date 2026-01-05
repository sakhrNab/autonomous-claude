"""
Configuration for the MCP Orchestrator.

Contains all configurable parameters including safety limits,
timeouts, and integration settings.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path
import os
import yaml


@dataclass
class SafetyConfig:
    """Safety limits that cannot be overridden without authorization."""
    max_iterations: int = 100
    max_time_seconds: int = 3600  # 1 hour
    max_budget_usd: float = 100.0
    max_retries_per_task: int = 5
    require_approval_above_cost: float = 50.0
    destructive_actions_require_approval: bool = True


@dataclass
class AgentConfig:
    """Configuration for agent behavior."""
    default_timeout_seconds: int = 300
    max_concurrent_agents: int = 10
    agent_heartbeat_interval: int = 30


@dataclass
class HookConfig:
    """Configuration for hooks."""
    stop_hook_enabled: bool = True
    pre_step_hook_enabled: bool = True
    post_step_hook_enabled: bool = True
    approval_hook_timeout_seconds: int = 3600


@dataclass
class StateConfig:
    """Configuration for state storage."""
    database_path: str = "state/sessions.db"
    memory_database_path: str = "state/memory.db"
    audit_log_path: str = "state/audit.log"
    task_ledger_path: str = "to-do.md"
    tasks_json_path: str = "tasks.json"


@dataclass
class IntegrationConfig:
    """Configuration for external integrations."""
    n8n_base_url: Optional[str] = None
    n8n_api_key: Optional[str] = None
    pipeline_webhook_url: Optional[str] = None
    slack_webhook_url: Optional[str] = None
    openai_api_key: Optional[str] = None
    google_cloud_project: Optional[str] = None


@dataclass
class Config:
    """Master configuration for the MCP Orchestrator."""
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    agents: AgentConfig = field(default_factory=AgentConfig)
    hooks: HookConfig = field(default_factory=HookConfig)
    state: StateConfig = field(default_factory=StateConfig)
    integrations: IntegrationConfig = field(default_factory=IntegrationConfig)

    # Environment
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    @classmethod
    def load_from_file(cls, path: str) -> "Config":
        """Load configuration from a YAML file."""
        with open(path, 'r') as f:
            data = yaml.safe_load(f)

        config = cls()

        if 'safety' in data:
            config.safety = SafetyConfig(**data['safety'])
        if 'agents' in data:
            config.agents = AgentConfig(**data['agents'])
        if 'hooks' in data:
            config.hooks = HookConfig(**data['hooks'])
        if 'state' in data:
            config.state = StateConfig(**data['state'])
        if 'integrations' in data:
            config.integrations = IntegrationConfig(**data['integrations'])

        config.environment = data.get('environment', 'development')
        config.debug = data.get('debug', True)
        config.log_level = data.get('log_level', 'INFO')

        return config

    @classmethod
    def load_from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        config = cls()

        # Safety config from env
        if os.getenv('MAX_ITERATIONS'):
            config.safety.max_iterations = int(os.getenv('MAX_ITERATIONS'))
        if os.getenv('MAX_TIME_SECONDS'):
            config.safety.max_time_seconds = int(os.getenv('MAX_TIME_SECONDS'))
        if os.getenv('MAX_BUDGET_USD'):
            config.safety.max_budget_usd = float(os.getenv('MAX_BUDGET_USD'))

        # Integration config from env
        config.integrations.n8n_base_url = os.getenv('N8N_BASE_URL')
        config.integrations.n8n_api_key = os.getenv('N8N_API_KEY')
        config.integrations.openai_api_key = os.getenv('OPENAI_API_KEY')
        config.integrations.slack_webhook_url = os.getenv('SLACK_WEBHOOK_URL')

        config.environment = os.getenv('ENVIRONMENT', 'development')
        config.debug = os.getenv('DEBUG', 'true').lower() == 'true'
        config.log_level = os.getenv('LOG_LEVEL', 'INFO')

        return config

    def validate(self) -> List[str]:
        """Validate configuration and return list of errors."""
        errors = []

        if self.safety.max_iterations < 1:
            errors.append("max_iterations must be at least 1")
        if self.safety.max_time_seconds < 1:
            errors.append("max_time_seconds must be at least 1")
        if self.safety.max_budget_usd < 0:
            errors.append("max_budget_usd cannot be negative")

        return errors
