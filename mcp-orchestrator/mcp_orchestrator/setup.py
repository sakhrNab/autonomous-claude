"""
Setup utilities to install agents, hooks, and skills into a project.

This makes Claude Code aware of the custom agents/hooks/skills when
running in that project directory.
"""

import shutil
from pathlib import Path
from typing import Optional


def setup_project(
    project_path: str = ".",
    include_agents: bool = True,
    include_skills: bool = True,
    include_hooks: bool = True,
    include_plugins: bool = True,
    force: bool = False,
) -> dict:
    """
    Set up a project to use the MCP Orchestrator's agents, hooks, and skills.

    This copies the .claude/ directory to your project so Claude Code
    can automatically use the custom agents, hooks, and skills.

    Args:
        project_path: Path to your project
        include_agents: Copy agent definitions
        include_skills: Copy skill definitions
        include_hooks: Copy hook configuration
        force: Overwrite existing files

    Returns:
        Dict with setup results

    Example:
        from mcp_orchestrator import setup_project

        # Set up current project
        setup_project(".")

        # Now run Claude Code in your project - it will use the agents!
    """
    project = Path(project_path).resolve()
    sdk_root = Path(__file__).parent.parent
    source_claude = sdk_root / ".claude"
    target_claude = project / ".claude"

    results = {
        "project": str(project),
        "agents_copied": [],
        "skills_copied": [],
        "hooks_copied": False,
        "errors": [],
    }

    if not source_claude.exists():
        results["errors"].append(f"Source .claude/ not found at {source_claude}")
        return results

    # Create .claude directory
    target_claude.mkdir(parents=True, exist_ok=True)

    # Copy agents
    if include_agents:
        source_agents = source_claude / "agents"
        target_agents = target_claude / "agents"
        if source_agents.exists():
            target_agents.mkdir(exist_ok=True)
            for agent_file in source_agents.glob("*.md"):
                target_file = target_agents / agent_file.name
                if not target_file.exists() or force:
                    shutil.copy2(agent_file, target_file)
                    results["agents_copied"].append(agent_file.name)

    # Copy skills
    if include_skills:
        source_skills = source_claude / "skills"
        target_skills = target_claude / "skills"
        if source_skills.exists():
            for skill_dir in source_skills.iterdir():
                if skill_dir.is_dir():
                    target_skill = target_skills / skill_dir.name
                    target_skill.mkdir(parents=True, exist_ok=True)
                    skill_md = skill_dir / "SKILL.md"
                    if skill_md.exists():
                        target_md = target_skill / "SKILL.md"
                        if not target_md.exists() or force:
                            shutil.copy2(skill_md, target_md)
                            results["skills_copied"].append(skill_dir.name)

    # Copy hooks
    if include_hooks:
        source_hooks = source_claude / "hooks"
        target_hooks = target_claude / "hooks"
        if source_hooks.exists():
            target_hooks.mkdir(exist_ok=True)
            hooks_json = source_hooks / "hooks.json"
            if hooks_json.exists():
                target_json = target_hooks / "hooks.json"
                if not target_json.exists() or force:
                    shutil.copy2(hooks_json, target_json)
                    results["hooks_copied"] = True

    # Copy plugins
    results["plugins_copied"] = []
    if include_plugins:
        source_plugins = source_claude / "plugins"
        target_plugins = target_claude / "plugins"
        if source_plugins.exists():
            for plugin_dir in source_plugins.iterdir():
                if plugin_dir.is_dir():
                    target_plugin = target_plugins / plugin_dir.name
                    if not target_plugin.exists() or force:
                        shutil.copytree(plugin_dir, target_plugin, dirs_exist_ok=True)
                        results["plugins_copied"].append(plugin_dir.name)

    # Create/update .claude/settings.json with commit protection
    settings_file = target_claude / "settings.json"
    settings = {
        "permissions": {
            "allow_commit": False,  # Never auto-commit
            "require_commit_confirmation": True,
        },
        "agents": {
            "enabled": True,
            "auto_delegate": True,
        },
        "hooks": {
            "enabled": True,
        },
    }

    import json
    if settings_file.exists() and not force:
        # Merge with existing
        try:
            existing = json.loads(settings_file.read_text())
            # Keep existing permissions if set
            if "permissions" in existing:
                settings["permissions"].update(existing["permissions"])
        except:
            pass

    settings_file.write_text(json.dumps(settings, indent=2))
    results["settings_updated"] = True

    return results


def list_available_agents() -> list:
    """List all available agents from the SDK."""
    sdk_root = Path(__file__).parent.parent
    agents_dir = sdk_root / ".claude" / "agents"

    agents = []
    if agents_dir.exists():
        for agent_file in agents_dir.glob("*.md"):
            agents.append({
                "name": agent_file.stem,
                "file": str(agent_file),
            })
    return agents


def list_available_skills() -> list:
    """List all available skills from the SDK."""
    sdk_root = Path(__file__).parent.parent
    skills_dir = sdk_root / ".claude" / "skills"

    skills = []
    if skills_dir.exists():
        for skill_dir in skills_dir.iterdir():
            if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                skills.append({
                    "name": skill_dir.name,
                    "file": str(skill_dir / "SKILL.md"),
                })
    return skills


# CLI entry point
def main():
    """CLI tool to set up a project."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Set up a project to use MCP Orchestrator agents, hooks, and skills"
    )
    parser.add_argument(
        "project_path",
        nargs="?",
        default=".",
        help="Path to your project (default: current directory)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files"
    )
    parser.add_argument(
        "--no-agents",
        action="store_true",
        help="Don't copy agents"
    )
    parser.add_argument(
        "--no-skills",
        action="store_true",
        help="Don't copy skills"
    )
    parser.add_argument(
        "--no-hooks",
        action="store_true",
        help="Don't copy hooks"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available agents and skills"
    )

    args = parser.parse_args()

    if args.list:
        print("Available Agents:")
        for agent in list_available_agents():
            print(f"  - {agent['name']}")
        print("\nAvailable Skills:")
        for skill in list_available_skills():
            print(f"  - {skill['name']}")
        return

    results = setup_project(
        project_path=args.project_path,
        include_agents=not args.no_agents,
        include_skills=not args.no_skills,
        include_hooks=not args.no_hooks,
        force=args.force,
    )

    print(f"Set up project: {results['project']}")
    print(f"Agents copied: {', '.join(results['agents_copied']) or 'none'}")
    print(f"Skills copied: {', '.join(results['skills_copied']) or 'none'}")
    print(f"Plugins copied: {', '.join(results.get('plugins_copied', [])) or 'none'}")
    print(f"Hooks copied: {results['hooks_copied']}")
    print(f"Settings updated: {results.get('settings_updated', False)}")

    if results["errors"]:
        print(f"Errors: {results['errors']}")


if __name__ == "__main__":
    main()
