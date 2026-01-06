"""
SDK Hook Definitions
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pathlib import Path
import json


@dataclass
class Hook:
    """
    Hook configuration for lifecycle events.

    Example:
        format_hook = Hook(
            event="PostToolUse",
            matcher="Write|Edit",
            command="prettier --write $FILE"
        )
    """
    event: str  # PreToolUse, PostToolUse, SubagentStop, etc.
    matcher: str  # Tool name pattern or *
    command: str
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-compatible dict."""
        return {
            "matcher": self.matcher,
            "hooks": [
                {
                    "type": "command",
                    "command": self.command,
                }
            ]
        }


class HooksConfig:
    """
    Manage hooks configuration.

    Example:
        config = HooksConfig()
        config.add(Hook("PostToolUse", "Write|Edit", "eslint --fix $FILE"))
        config.save()
    """

    def __init__(self, hooks_dir: str = ".claude/hooks"):
        self.hooks_dir = Path(hooks_dir)
        self.hooks: Dict[str, List[Hook]] = {}
        self._load()

    def _load(self):
        """Load existing hooks."""
        hooks_file = self.hooks_dir / "hooks.json"
        if hooks_file.exists():
            try:
                data = json.loads(hooks_file.read_text())
                # Parse back into Hook objects
                for event, matchers in data.get("hooks", {}).items():
                    self.hooks[event] = []
                    for matcher_config in matchers:
                        for hook_config in matcher_config.get("hooks", []):
                            self.hooks[event].append(Hook(
                                event=event,
                                matcher=matcher_config.get("matcher", "*"),
                                command=hook_config.get("command", ""),
                            ))
            except Exception:
                pass

    def add(self, hook: Hook):
        """Add a hook."""
        if hook.event not in self.hooks:
            self.hooks[hook.event] = []
        self.hooks[hook.event].append(hook)

    def remove(self, event: str, matcher: str):
        """Remove hooks matching event and matcher."""
        if event in self.hooks:
            self.hooks[event] = [h for h in self.hooks[event] if h.matcher != matcher]

    def save(self):
        """Save hooks to file."""
        self.hooks_dir.mkdir(parents=True, exist_ok=True)

        output = {"hooks": {}}
        for event, hooks in self.hooks.items():
            output["hooks"][event] = [h.to_dict() for h in hooks]

        (self.hooks_dir / "hooks.json").write_text(
            json.dumps(output, indent=2)
        )


# Pre-defined hooks

FORMAT_TYPESCRIPT_HOOK = Hook(
    event="PostToolUse",
    matcher="Write|Edit",
    command='jq -r \'.tool_input.file_path\' | { read file; [[ "$file" == *.ts ]] && npx prettier --write "$file"; }'
)

LOG_COMMANDS_HOOK = Hook(
    event="PreToolUse",
    matcher="Bash",
    command='jq -r \'"\(.tool_input.command) - \(.tool_input.description // "No desc")"\' >> ~/.claude/command-log.txt'
)

UPDATE_TODO_HOOK = Hook(
    event="SubagentStop",
    matcher="*",
    command='echo "[$(date)] Agent completed" >> pipeline.log'
)
