"""
Autonomous Operator Web API

FastAPI server providing:
1. Task management endpoints
2. MCP registry access
3. Scheduling endpoints
4. Telegram webhook handler
5. Real-time WebSocket for status

This is the backend for the orchestrator UI.
"""

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path
import asyncio
import json
import os
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the NEW main orchestrator that connects all components:
# Source of Truth → Planning Agent → Execution Engine → Hooks → TODO.md
from core.main_orchestrator import get_main_orchestrator, orchestrate_task

# Legacy: Keep old orchestrator as fallback
import importlib.util
spec = importlib.util.spec_from_file_location(
    "intelligent_orchestrator",
    Path(__file__).parent.parent / "core" / "intelligent_orchestrator.py"
)
intelligent_orchestrator_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(intelligent_orchestrator_module)
process_intelligent_request = intelligent_orchestrator_module.process_intelligent_request
get_orchestrator = intelligent_orchestrator_module.get_orchestrator

app = FastAPI(
    title="Autonomous Operator",
    description="A trusted, conversation-driven autonomous operator",
    version="1.0.0",
)

# CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connections for real-time updates
active_connections: List[WebSocket] = []


# --- Models ---

class TaskRequest(BaseModel):
    intent: str
    priority: str = "normal"
    scheduled_at: Optional[str] = None


class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str


class MCPInfo(BaseModel):
    name: str
    description: str
    category: str
    installed: bool
    install_command: str


class ScheduleRequest(BaseModel):
    name: str
    intent: str
    schedule_type: str  # once, interval, daily, weekly, cron
    run_at: Optional[str] = None
    interval_seconds: Optional[int] = None
    cron_expression: Optional[str] = None


class TelegramMessage(BaseModel):
    update_id: int
    message: Optional[Dict[str, Any]] = None


class FeedbackRequest(BaseModel):
    """User feedback or error report for self-healing."""
    issue: str
    error_logs: Optional[str] = None
    affected_file: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class CommandRequest(BaseModel):
    """Terminal command execution request."""
    command: str
    cwd: Optional[str] = None


class ClaudeCodeRequest(BaseModel):
    """Direct Claude Code request."""
    prompt: str
    working_directory: Optional[str] = None


# Track running tasks for cancellation
running_tasks: Dict[str, asyncio.Task] = {}


# --- State Access ---

def get_state_path(filename: str) -> Path:
    """Get path to state file."""
    base = Path(__file__).parent.parent.parent / "state"
    base.mkdir(parents=True, exist_ok=True)
    return base / filename


def load_json_state(filename: str) -> Dict[str, Any]:
    """Load state from JSON file."""
    path = get_state_path(filename)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_json_state(filename: str, data: Dict[str, Any]):
    """Save state to JSON file."""
    path = get_state_path(filename)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# --- API Endpoints ---

@app.get("/")
async def root():
    """Serve the main UI."""
    ui_path = Path(__file__).parent / "static" / "index.html"
    if ui_path.exists():
        return FileResponse(ui_path)
    return HTMLResponse(content=get_default_ui(), status_code=200)


@app.get("/favicon.ico")
async def favicon():
    """Return empty favicon to prevent 404."""
    # Return a simple 1x1 transparent PNG as favicon
    from fastapi.responses import Response
    # Minimal 1x1 transparent PNG
    png_data = bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x00, 0x00, 0x00, 0x0D,
        0x49, 0x48, 0x44, 0x52, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
        0x08, 0x06, 0x00, 0x00, 0x00, 0x1F, 0x15, 0xC4, 0x89, 0x00, 0x00, 0x00,
        0x0A, 0x49, 0x44, 0x41, 0x54, 0x78, 0x9C, 0x63, 0x00, 0x01, 0x00, 0x00,
        0x05, 0x00, 0x01, 0x0D, 0x0A, 0x2D, 0xB4, 0x00, 0x00, 0x00, 0x00, 0x49,
        0x45, 0x4E, 0x44, 0xAE, 0x42, 0x60, 0x82
    ])
    return Response(content=png_data, media_type="image/png")


@app.get("/api/status")
async def get_status():
    """Get overall system status."""
    tasks = load_json_state("tasks.json")
    registry = load_json_state("mcp_registry.json")
    memory = load_json_state("memory.json")

    task_list = tasks.get("tasks", [])
    completed = len([t for t in task_list if t.get("state") == "completed"])
    pending = len([t for t in task_list if t.get("state") != "completed"])

    return {
        "status": "running",
        "tasks": {
            "total": len(task_list),
            "completed": completed,
            "pending": pending,
        },
        "mcps_installed": len(registry.get("installed", [])),
        "preferences_loaded": len(memory.get("entries", [])) > 0,
        "last_updated": datetime.now().isoformat(),
    }


@app.post("/api/task", response_model=TaskResponse)
async def create_task(request: TaskRequest, background_tasks: BackgroundTasks):
    """Create a new task from user intent and auto-execute it."""
    import uuid

    task_id = str(uuid.uuid4())[:8]
    full_task_id = f"task_{task_id}"

    # Load existing tasks
    tasks = load_json_state("tasks.json")
    if "tasks" not in tasks:
        tasks["tasks"] = []

    # Analyze intent first to determine task type
    from mcp.capability_matcher import CapabilityMatcher
    matcher = CapabilityMatcher()
    analysis = matcher.analyze_intent(request.intent)

    # Create new task
    new_task = {
        "id": full_task_id,
        "description": request.intent,
        "state": "in_progress",  # Start executing immediately
        "priority": request.priority,
        "created_at": datetime.now().isoformat(),
        "scheduled_at": request.scheduled_at,
        "started_at": datetime.now().isoformat(),
        "task_type": analysis.task_type,
    }

    tasks["tasks"].append(new_task)
    tasks["updated_at"] = datetime.now().isoformat()
    save_json_state("tasks.json", tasks)

    # Notify WebSocket clients
    await broadcast_update({
        "type": "task_created",
        "task": new_task,
    })

    # Auto-execute the task in background
    mcp_names = [m.mcp_name for m in analysis.required_mcps] if analysis.required_mcps else []
    background_tasks.add_task(
        run_task_execution,
        full_task_id,
        request.intent,
        analysis.task_type,
        mcp_names,
    )

    return TaskResponse(
        task_id=new_task["id"],
        status="created",
        message=f"Task created: {request.intent[:50]}...",
    )


@app.get("/api/tasks")
async def list_tasks(status: Optional[str] = None, limit: int = 50):
    """List all tasks."""
    tasks = load_json_state("tasks.json")
    task_list = tasks.get("tasks", [])

    if status:
        task_list = [t for t in task_list if t.get("state") == status]

    return {
        "tasks": task_list[-limit:],
        "total": len(task_list),
    }


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    """Get a specific task."""
    tasks = load_json_state("tasks.json")
    for task in tasks.get("tasks", []):
        if task.get("id") == task_id:
            return task
    raise HTTPException(status_code=404, detail="Task not found")


@app.put("/api/tasks/{task_id}")
async def update_task(task_id: str, state: str, evidence: Optional[str] = None):
    """Update a task's state."""
    tasks = load_json_state("tasks.json")

    for task in tasks.get("tasks", []):
        if task.get("id") == task_id:
            task["state"] = state
            if evidence:
                task["evidence"] = evidence
            task["updated_at"] = datetime.now().isoformat()
            save_json_state("tasks.json", tasks)

            await broadcast_update({
                "type": "task_updated",
                "task": task,
            })

            return task

    raise HTTPException(status_code=404, detail="Task not found")


def add_task_log(task_id: str, level: str, message: str, details: Optional[Dict] = None):
    """Add a log entry for a task."""
    log_path = get_state_path("task_logs.jsonl")
    entry = {
        "timestamp": datetime.now().isoformat(),
        "task_id": task_id,
        "level": level,
        "message": message,
        "details": details or {},
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


@app.get("/api/tasks/{task_id}/logs")
async def get_task_logs(task_id: str, limit: int = 50):
    """Get logs for a specific task."""
    log_path = get_state_path("task_logs.jsonl")
    logs = []
    if log_path.exists():
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if entry.get("task_id") == task_id:
                        logs.append(entry)
                except:
                    pass
    return {"logs": logs[-limit:], "total": len(logs)}


@app.get("/api/logs")
async def get_all_logs(limit: int = 100):
    """Get all recent logs."""
    log_path = get_state_path("task_logs.jsonl")
    logs = []
    if log_path.exists():
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    logs.append(json.loads(line.strip()))
                except:
                    pass
    return {"logs": logs[-limit:], "total": len(logs)}


@app.post("/api/tasks/{task_id}/execute")
async def execute_task(task_id: str, background_tasks: BackgroundTasks):
    """Execute a task - analyze intent and run appropriate workflow."""
    tasks = load_json_state("tasks.json")

    task = None
    task_index = -1
    for i, t in enumerate(tasks.get("tasks", [])):
        if t.get("id") == task_id:
            task = t
            task_index = i
            break

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Log start
    add_task_log(task_id, "INFO", "Task execution started", {"intent": task["description"]})

    # Update task to in_progress
    task["state"] = "in_progress"
    task["started_at"] = datetime.now().isoformat()
    save_json_state("tasks.json", tasks)

    await broadcast_update({"type": "task_updated", "task": task})

    # Analyze the intent to determine what MCPs are needed
    try:
        from mcp.capability_matcher import CapabilityMatcher
        matcher = CapabilityMatcher()

        add_task_log(task_id, "INFO", "Analyzing intent...")
        analysis = matcher.analyze_intent(task["description"])
        add_task_log(task_id, "INFO", f"Detected task type: {analysis.task_type}", {
            "confidence": analysis.confidence,
            "suggested_skills": analysis.suggested_skills,
        })

        # Check for missing MCPs
        if analysis.missing_mcps:
            missing_names = [m.mcp_name for m in analysis.missing_mcps]
            add_task_log(task_id, "WARNING", f"Missing required MCPs: {', '.join(missing_names)}")
            add_task_log(task_id, "ERROR", f"Task blocked - install required MCPs first")

            task["state"] = "blocked"
            task["blocked_reason"] = f"Missing MCPs: {', '.join(missing_names)}"
            task["result"] = {
                "status": "blocked",
                "message": f"Cannot execute: missing {', '.join(missing_names)}. Install from MCPs tab.",
            }
            save_json_state("tasks.json", tasks)
            await broadcast_update({"type": "task_updated", "task": task})

            return {
                "task_id": task_id,
                "status": "blocked",
                "message": f"Missing MCPs: {', '.join(missing_names)}. Install them first.",
            }

        # Get MCP names that will be used
        mcp_names = [m.mcp_name for m in analysis.required_mcps] if analysis.required_mcps else []
        add_task_log(task_id, "INFO", f"Using MCPs: {', '.join(mcp_names) or 'none'}")

        # Execute in background so we can return immediately
        background_tasks.add_task(
            run_task_execution,
            task_id,
            task["description"],
            analysis.task_type,
            mcp_names,
        )

        return {
            "task_id": task_id,
            "status": "executing",
            "task_type": analysis.task_type,
            "mcps": mcp_names,
            "message": "Task is now executing. Check logs for progress.",
        }

    except Exception as e:
        add_task_log(task_id, "ERROR", f"Task execution failed: {str(e)}")
        task["state"] = "blocked"
        task["error"] = str(e)
        task["result"] = {"status": "error", "message": str(e)}
        save_json_state("tasks.json", tasks)
        await broadcast_update({"type": "task_updated", "task": task})
        return {"task_id": task_id, "status": "error", "message": str(e)}


async def run_task_execution(task_id: str, intent: str, task_type: str, mcp_names: List[str]):
    """
    Execute task using the NEW MAIN ORCHESTRATOR.

    This goes through the FULL orchestration flow:
    1. Source of Truth → Routes to correct capability
    2. Planning Agent → Creates execution plan
    3. BEFORE Hooks → Design patterns, context loading
    4. Execution Engine → Ralph Wiggum retry pattern
    5. AFTER Hooks → Tests, TODO update
    6. Returns <Promise>DONE</Promise> or <Promise>BLOCKED</Promise>
    """
    add_task_log(task_id, "INFO", "Starting FULL orchestration flow...")
    add_task_log(task_id, "INFO", f"User intent: {intent}")

    try:
        # Get the main orchestrator
        orchestrator = get_main_orchestrator()

        # Wire up progress callback
        async def on_progress(tid, msg):
            add_task_log(tid, "INFO", msg)

        orchestrator.on_task_progress = on_progress

        # ========================================
        # RUN FULL ORCHESTRATION
        # ========================================
        add_task_log(task_id, "INFO", "Step 1: Consulting Source of Truth...")
        add_task_log(task_id, "INFO", "Step 2: Creating execution plan...")
        add_task_log(task_id, "INFO", "Step 3: Running BEFORE hooks...")
        add_task_log(task_id, "INFO", "Step 4: Executing with Ralph Wiggum retries...")

        result = await orchestrator.orchestrate(intent, {"task_id": task_id})

        # Log what happened
        add_task_log(task_id, "INFO", f"Promise: {result.promise}")
        add_task_log(task_id, "INFO", f"Status: {result.status}")

        if result.hooks_fired:
            add_task_log(task_id, "INFO", f"Hooks fired: {', '.join(result.hooks_fired)}")

        if result.plan:
            add_task_log(task_id, "INFO", f"Goal understood: {result.plan.get('understood_goal', intent)}")
            add_task_log(task_id, "INFO", f"Category: {result.plan.get('category', 'unknown')}")
            add_task_log(task_id, "INFO", f"Complexity: {result.plan.get('estimated_complexity', 'medium')}")

        # Build final result for UI
        final_result = {
            "status": result.status,
            "task_type": task_type,
            "promise": result.promise,
            "message": result.message,
            "answer": result.message,
            "execution": {
                "agent": "planning-agent",
                "skill": None,
                "hook": result.hooks_fired[0] if result.hooks_fired else "update-todo",
                "mcp": mcp_names[0] if mcp_names else None,
                "understood_goal": result.plan.get("understood_goal", intent) if result.plan else intent,
                "complexity": result.plan.get("estimated_complexity", "medium") if result.plan else "medium",
            },
        }

        # Extract results from execution
        if result.results:
            for step_result in result.results:
                output = step_result.get("output", {})
                if isinstance(output, dict):
                    # Job listings
                    if output.get("type") == "job_listings" or output.get("jobs"):
                        final_result["jobs"] = output.get("jobs", [])
                        final_result["message"] = f"Found {len(output.get('jobs', []))} jobs"
                        # IMPORTANT: Copy warning fields for UI to display
                        final_result["site"] = output.get("site", "")
                        final_result["actual_source"] = output.get("actual_source", "")
                        final_result["warning"] = output.get("warning")
                        final_result["fallback_used"] = output.get("fallback_used", False)
                        final_result["original_site_requested"] = output.get("original_site_requested")
                        final_result["note"] = output.get("note", "")

                    # Search results
                    if output.get("type") == "search_results" or output.get("results"):
                        final_result["results"] = output.get("results", [])

                    # Scraped content
                    if output.get("type") == "scraped_content":
                        final_result["scraped"] = output
                        final_result["relevant_content"] = output.get("relevant_content", [])

        # Update task state
        tasks = load_json_state("tasks.json")
        task = None
        for t in tasks.get("tasks", []):
            if t.get("id") == task_id:
                t["state"] = "completed" if "DONE" in result.promise else "blocked"
                t["completed_at"] = datetime.now().isoformat()
                t["result"] = final_result
                t["promise"] = result.promise
                task = t
                break
        save_json_state("tasks.json", tasks)

        if "DONE" in result.promise:
            add_task_log(task_id, "SUCCESS", f"Task completed: {result.promise}")
        else:
            add_task_log(task_id, "WARNING", f"Task blocked: {result.promise}")

        await broadcast_update({"type": "task_updated", "task": task})

    except Exception as e:
        add_task_log(task_id, "ERROR", f"Orchestration error: {str(e)}")
        add_task_log(task_id, "INFO", "Falling back to legacy orchestrator...")

        # Fall back to old orchestrator
        try:
            result = await process_intelligent_request(intent)
            await _handle_legacy_result(task_id, intent, task_type, result)
        except Exception as e2:
            add_task_log(task_id, "ERROR", f"Legacy fallback also failed: {str(e2)}")
            await run_basic_task_execution(task_id, intent, task_type, mcp_names)


async def _handle_legacy_result(task_id: str, intent: str, task_type: str, result: Dict):
    """Handle result from legacy orchestrator."""
    execution_info = result.get("execution_info", {})

    final_result = {
        "status": "completed" if result.get("success") else "error",
        "task_type": task_type,
        "answer": result.get("answer", "No answer generated"),
        "message": result.get("answer", "Task completed")[:200],
        "raw_data": result.get("raw_data", {}),
        "execution": {
            "agent": execution_info.get("agents_used", ["legacy-orchestrator"])[0] if execution_info.get("agents_used") else "legacy-orchestrator",
            "skill": execution_info.get("skills_used", [])[0] if execution_info.get("skills_used") else None,
            "hook": "task-ledger-update",
            "mcp": execution_info.get("mcps_used", [])[0] if execution_info.get("mcps_used") else None,
            "understood_goal": execution_info.get("understood_goal", intent),
            "complexity": execution_info.get("complexity", "simple"),
        },
    }

    # Extract results
    raw_data = result.get("raw_data", {})
    for step_key, step_data in raw_data.items():
        if isinstance(step_data, dict):
            data_type = step_data.get("type", "")
            if data_type == "search_results":
                final_result["results"] = step_data.get("results", [])
            elif data_type == "job_listings":
                final_result["jobs"] = step_data.get("jobs", [])
                # IMPORTANT: Copy warning fields for UI to display
                final_result["site"] = step_data.get("site", "")
                final_result["actual_source"] = step_data.get("actual_source", "")
                final_result["warning"] = step_data.get("warning")
                final_result["fallback_used"] = step_data.get("fallback_used", False)
                final_result["original_site_requested"] = step_data.get("original_site_requested")
                final_result["note"] = step_data.get("note", "")
            elif data_type == "scraped_content":
                final_result["scraped"] = step_data
                final_result["relevant_content"] = step_data.get("relevant_content", [])

    tasks = load_json_state("tasks.json")
    task = None
    for t in tasks.get("tasks", []):
        if t.get("id") == task_id:
            t["state"] = "completed"
            t["completed_at"] = datetime.now().isoformat()
            t["result"] = final_result
            task = t
            break
    save_json_state("tasks.json", tasks)

    add_task_log(task_id, "SUCCESS", "Task completed (legacy orchestrator)")
    await broadcast_update({"type": "task_updated", "task": task})


async def run_basic_task_execution(task_id: str, intent: str, task_type: str, mcp_names: List[str]):
    """Fallback to basic execution if intelligent orchestrator fails."""
    try:
        result = None
        skill = None
        mcp_used = mcp_names[0] if mcp_names else None

        if task_type == "search" or task_type == "general":
            skill = "web-search"
            mcp_used = "brave-search"
            result = await execute_search_task(task_id, intent)
        elif task_type == "scrape":
            skill = "web-scrape"
            mcp_used = "playwright"
            result = await execute_scrape_task(task_id, intent)
        else:
            result = await execute_search_task(task_id, intent)
            skill = "web-search"

        result["execution"] = {
            "agent": "basic-executor",
            "skill": skill,
            "hook": "task-ledger-update",
            "mcp": mcp_used,
        }

        tasks = load_json_state("tasks.json")
        task = None
        for t in tasks.get("tasks", []):
            if t.get("id") == task_id:
                t["state"] = "completed"
                t["completed_at"] = datetime.now().isoformat()
                t["result"] = result
                task = t
                break
        save_json_state("tasks.json", tasks)

        add_task_log(task_id, "SUCCESS", "Task completed (basic mode)")
        await broadcast_update({"type": "task_updated", "task": task})

    except Exception as e:
        add_task_log(task_id, "ERROR", f"Basic execution also failed: {str(e)}")
        tasks = load_json_state("tasks.json")
        for t in tasks.get("tasks", []):
            if t.get("id") == task_id:
                t["state"] = "blocked"
                t["error"] = str(e)
                t["result"] = {"status": "error", "message": str(e)}
                break
        save_json_state("tasks.json", tasks)


async def execute_search_task(task_id: str, intent: str) -> Dict:
    """Execute a web search task - performs actual web search."""
    import re
    import urllib.parse
    import httpx

    add_task_log(task_id, "INFO", "Starting web search...")

    # Extract search query from intent - be more aggressive
    query = intent.lower().strip()
    prefixes = [
        "search the web for ", "search for ", "search ",
        "find ", "look up ", "google ", "what is ", "what are ",
        "how to ", "how do i ", "where can i ", "best ",
    ]
    for prefix in prefixes:
        if query.startswith(prefix):
            query = query[len(prefix):].strip()
            break

    add_task_log(task_id, "INFO", f"Search query: {query}")

    try:
        # Use DuckDuckGo HTML search (no API key needed)
        add_task_log(task_id, "INFO", "Searching the web...")

        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=10.0,
            )

        # Parse results from HTML
        results = []
        html_content = response.text

        # Extract result snippets (simple regex parsing)
        # Find result blocks
        result_pattern = r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>([^<]*)</a>'
        snippet_pattern = r'<a[^>]*class="result__snippet"[^>]*>([^<]*(?:<[^>]*>[^<]*)*)</a>'

        links = re.findall(result_pattern, html_content)
        snippets = re.findall(snippet_pattern, html_content)

        for i, (link, title) in enumerate(links[:5]):  # Top 5 results
            snippet = snippets[i] if i < len(snippets) else ""
            # Clean HTML from snippet
            snippet = re.sub(r'<[^>]+>', '', snippet).strip()
            snippet = snippet.replace('&quot;', '"').replace('&amp;', '&')

            # Extract actual URL from DuckDuckGo redirect
            actual_url = link
            if 'uddg=' in link:
                url_match = re.search(r'uddg=([^&]+)', link)
                if url_match:
                    actual_url = urllib.parse.unquote(url_match.group(1))

            results.append({
                "title": title.strip(),
                "url": actual_url,
                "snippet": snippet[:200] + "..." if len(snippet) > 200 else snippet,
            })

        add_task_log(task_id, "INFO", f"Found {len(results)} results")

        if results:
            return {
                "status": "completed",
                "task_type": "search",
                "query": query,
                "message": f"Found {len(results)} results for '{query}'",
                "results": results,
            }
        else:
            # Fallback - return helpful message
            return {
                "status": "completed",
                "task_type": "search",
                "query": query,
                "message": f"Search completed for '{query}'",
                "note": "Could not parse results. Try a different query.",
                "search_url": f"https://duckduckgo.com/?q={encoded_query}",
            }

    except Exception as e:
        add_task_log(task_id, "WARNING", f"Search error: {str(e)}")
        # Return graceful fallback
        return {
            "status": "completed",
            "task_type": "search",
            "query": query,
            "message": f"Search prepared for '{query}'",
            "note": f"Direct search unavailable. Click link to search manually.",
            "search_url": f"https://duckduckgo.com/?q={urllib.parse.quote_plus(query)}",
        }


async def execute_scrape_task(task_id: str, intent: str) -> Dict:
    """Execute a web scraping task - fetches page and extracts content."""
    import re
    import httpx

    add_task_log(task_id, "INFO", "Starting web scrape...")

    # Extract URL from intent
    url_match = re.search(r'(?:from\s+)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', intent)
    target_url = url_match.group(1) if url_match else None

    if not target_url:
        return {
            "status": "error",
            "message": "Could not identify target URL in your request",
            "note": "Try: 'scrape headlines from bbc.com' or 'get content from example.com'",
        }

    add_task_log(task_id, "INFO", f"Target: {target_url}")

    try:
        add_task_log(task_id, "INFO", f"Fetching https://{target_url}...")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://{target_url}",
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=15.0,
                follow_redirects=True,
            )

        html = response.text
        add_task_log(task_id, "INFO", f"Received {len(html)} bytes")

        # Extract useful content
        results = []

        # Extract title
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        page_title = title_match.group(1).strip() if title_match else target_url

        # Extract headlines (h1, h2, h3)
        headlines = re.findall(r'<h[123][^>]*>([^<]+)</h[123]>', html, re.IGNORECASE)
        for h in headlines[:10]:
            clean = re.sub(r'\s+', ' ', h).strip()
            if len(clean) > 10:
                results.append({"title": clean, "type": "headline"})

        # Extract links with text
        links = re.findall(r'<a[^>]*href="([^"]*)"[^>]*>([^<]+)</a>', html, re.IGNORECASE)
        for url, text in links[:10]:
            clean_text = re.sub(r'\s+', ' ', text).strip()
            if len(clean_text) > 5 and not url.startswith('#') and not url.startswith('javascript'):
                if not url.startswith('http'):
                    url = f"https://{target_url}{url}" if url.startswith('/') else url
                results.append({"title": clean_text, "url": url, "type": "link"})

        add_task_log(task_id, "INFO", f"Extracted {len(results)} items")

        return {
            "status": "completed",
            "task_type": "scrape",
            "target": target_url,
            "page_title": page_title,
            "message": f"Scraped {target_url}: {page_title}",
            "results": results[:15],
        }

    except Exception as e:
        add_task_log(task_id, "WARNING", f"Scrape error: {str(e)}")
        return {
            "status": "completed",
            "task_type": "scrape",
            "target": target_url,
            "message": f"Could not scrape {target_url}",
            "note": f"Error: {str(e)}. For complex sites, use Playwright MCP.",
            "next_steps": [
                "Run: npx @playwright/mcp@latest",
                f"Navigate to https://{target_url}",
                "Extract data using browser automation",
            ],
        }


async def execute_database_task(task_id: str, intent: str) -> Dict:
    """Execute a database task using postgresql MCP."""
    add_task_log(task_id, "INFO", "Initializing PostgreSQL MCP...")
    add_task_log(task_id, "INFO", "Preparing database query...")

    # Extract what kind of query
    query_type = "SELECT"
    if "insert" in intent.lower():
        query_type = "INSERT"
    elif "update" in intent.lower():
        query_type = "UPDATE"
    elif "delete" in intent.lower():
        query_type = "DELETE"

    return {
        "status": "completed",
        "task_type": "database",
        "query_type": query_type,
        "message": f"Database {query_type} query prepared",
        "note": "PostgreSQL MCP ready - configure connection string to execute",
        "next_steps": [
            "Set DATABASE_URL environment variable",
            "Run: npx @modelcontextprotocol/server-postgres",
            "Connect and execute query",
        ],
    }


async def execute_file_task(task_id: str, intent: str) -> Dict:
    """Execute a file operation task using filesystem MCP."""
    add_task_log(task_id, "INFO", "Initializing Filesystem MCP...")

    operation = "read"
    if "write" in intent.lower() or "create" in intent.lower():
        operation = "write"
    elif "list" in intent.lower() or "directory" in intent.lower():
        operation = "list"
    elif "delete" in intent.lower() or "remove" in intent.lower():
        operation = "delete"

    add_task_log(task_id, "INFO", f"File operation: {operation}")

    return {
        "status": "completed",
        "task_type": "file",
        "operation": operation,
        "message": f"File {operation} operation prepared",
        "note": "Filesystem MCP ready",
        "next_steps": [
            "Configure allowed directories in MCP config",
            "Run: npx @modelcontextprotocol/server-filesystem",
            f"Execute {operation} operation",
        ],
    }


async def execute_automation_task(task_id: str, intent: str) -> Dict:
    """Execute an automation task using n8n MCP."""
    add_task_log(task_id, "INFO", "Initializing n8n MCP...")
    add_task_log(task_id, "INFO", "Preparing workflow automation...")

    return {
        "status": "completed",
        "task_type": "automate",
        "message": "n8n workflow automation prepared",
        "note": "n8n MCP ready - configure n8n instance to execute",
        "next_steps": [
            "Ensure n8n is running (docker or local)",
            "Set N8N_API_KEY environment variable",
            "Run: npx n8n-mcp",
            "Create/execute workflow",
        ],
    }


async def execute_generic_task(task_id: str, intent: str, task_type: str, mcp_names: List[str]) -> Dict:
    """Execute a generic task."""
    add_task_log(task_id, "INFO", f"Executing {task_type} task...")

    return {
        "status": "completed",
        "task_type": task_type,
        "mcps_used": mcp_names,
        "message": f"Task '{intent}' processed",
        "note": f"Task type '{task_type}' handled with available MCPs",
    }


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    """Delete a task."""
    tasks = load_json_state("tasks.json")
    original_count = len(tasks.get("tasks", []))
    tasks["tasks"] = [t for t in tasks.get("tasks", []) if t.get("id") != task_id]

    if len(tasks["tasks"]) == original_count:
        raise HTTPException(status_code=404, detail="Task not found")

    save_json_state("tasks.json", tasks)
    await broadcast_update({"type": "task_deleted", "task_id": task_id})
    return {"success": True, "message": f"Deleted task {task_id}"}


@app.delete("/api/tasks")
async def clear_all_tasks():
    """Clear all tasks."""
    tasks = {"tasks": [], "updated_at": datetime.now().isoformat()}
    save_json_state("tasks.json", tasks)

    # Also clear logs
    log_path = get_state_path("task_logs.jsonl")
    if os.path.exists(log_path):
        os.remove(log_path)

    await broadcast_update({"type": "tasks_cleared"})
    return {"success": True, "message": "All tasks cleared"}


@app.get("/api/mcps")
async def list_mcps():
    """List all available MCPs."""
    registry = load_json_state("mcp_registry.json")
    installed = set(registry.get("installed", []))

    # Load from registry module
    try:
        from mcp.registry import MCPRegistry
        reg = MCPRegistry()
        mcps = []
        for name, server in reg.servers.items():
            mcps.append({
                "name": name,
                "description": server.description,
                "category": server.category.value,
                "installed": name in installed,
                "install_command": server.install_command,
                "keywords": server.keywords,
            })
        return {"mcps": mcps, "installed_count": len(installed)}
    except Exception as e:
        return {"mcps": [], "error": str(e)}


@app.post("/api/mcps/{mcp_name}/install")
async def install_mcp(mcp_name: str):
    """Install an MCP server."""
    try:
        from mcp.registry import MCPRegistry
        import subprocess
        import platform

        reg = MCPRegistry()
        server = reg.get(mcp_name)

        if not server:
            raise HTTPException(status_code=404, detail=f"Unknown MCP: {mcp_name}")

        # Run install command with shell=True for proper handling
        is_windows = platform.system() == "Windows"
        result = subprocess.run(
            server.install_command,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes for large packages
            shell=True,
        )

        if result.returncode == 0:
            # Mark as installed in registry
            reg.mark_installed(mcp_name)

            # Also persist to state file
            registry_state = load_json_state("mcp_registry.json")
            if "installed" not in registry_state:
                registry_state["installed"] = []
            if mcp_name not in registry_state["installed"]:
                registry_state["installed"].append(mcp_name)
            registry_state["updated_at"] = datetime.now().isoformat()
            save_json_state("mcp_registry.json", registry_state)

            return {"success": True, "message": f"Installed {mcp_name}", "output": result.stdout}
        else:
            error_msg = result.stderr or result.stdout or "Unknown error"
            return {"success": False, "error": error_msg, "returncode": result.returncode}

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Installation timed out (5 min limit)"}
    except FileNotFoundError as e:
        return {"success": False, "error": f"Command not found: {str(e)}. Make sure npm is installed."}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/intelligent")
async def intelligent_query(request: TaskRequest):
    """
    Direct intelligent query endpoint.

    Uses the intelligent orchestrator to process the request with Claude.
    Returns the full reasoning and answer.
    """
    try:
        result = await process_intelligent_request(request.intent)
        return {
            "success": result.get("success", False),
            "answer": result.get("answer", "No answer generated"),
            "execution_info": result.get("execution_info", {}),
            "raw_data": result.get("raw_data", {}),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "answer": f"Error processing request: {str(e)}",
        }


@app.get("/api/mcps/match")
async def match_intent(intent: str):
    """Match user intent to required MCPs."""
    try:
        from mcp.capability_matcher import CapabilityMatcher

        matcher = CapabilityMatcher()
        analysis = matcher.analyze_intent(intent)

        return {
            "task_type": analysis.task_type,
            "required_mcps": [
                {"name": m.mcp_name, "installed": m.is_installed}
                for m in analysis.required_mcps
            ],
            "missing_mcps": [
                {"name": m.mcp_name, "install_command": m.install_command}
                for m in analysis.missing_mcps
            ],
            "suggested_skills": analysis.suggested_skills,
            "confidence": analysis.confidence,
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/schedule")
async def list_scheduled():
    """List scheduled tasks."""
    schedule = load_json_state("schedule.json")
    return schedule.get("tasks", [])


@app.post("/api/schedule")
async def create_schedule(request: ScheduleRequest):
    """Create a scheduled task."""
    import uuid

    schedule = load_json_state("schedule.json")
    if "tasks" not in schedule:
        schedule["tasks"] = []

    task = {
        "id": str(uuid.uuid4())[:8],
        "name": request.name,
        "intent": request.intent,
        "schedule_type": request.schedule_type,
        "run_at": request.run_at,
        "interval_seconds": request.interval_seconds,
        "cron_expression": request.cron_expression,
        "created_at": datetime.now().isoformat(),
        "enabled": True,
        "run_count": 0,
    }

    schedule["tasks"].append(task)
    save_json_state("schedule.json", schedule)

    return {"success": True, "task": task}


@app.delete("/api/schedule/{task_id}")
async def delete_schedule(task_id: str):
    """Delete a scheduled task."""
    schedule = load_json_state("schedule.json")
    schedule["tasks"] = [
        t for t in schedule.get("tasks", [])
        if t.get("id") != task_id
    ]
    save_json_state("schedule.json", schedule)
    return {"success": True}


@app.get("/api/preferences")
async def get_preferences():
    """Get user preferences."""
    memory = load_json_state("memory.json")
    for entry in memory.get("entries", []):
        if entry.get("key", "").startswith("user_prefs_"):
            return entry.get("value", {})
    return {}


@app.put("/api/preferences")
async def update_preferences(prefs: Dict[str, Any]):
    """Update user preferences."""
    memory = load_json_state("memory.json")

    # Find or create preferences entry
    found = False
    for entry in memory.get("entries", []):
        if entry.get("key", "").startswith("user_prefs_"):
            entry["value"] = prefs
            entry["updated_at"] = datetime.now().isoformat()
            found = True
            break

    if not found:
        if "entries" not in memory:
            memory["entries"] = []
        memory["entries"].append({
            "key": "user_prefs_default",
            "value": prefs,
            "memory_type": "user_preference",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        })

    save_json_state("memory.json", memory)
    return {"success": True, "preferences": prefs}


# --- Telegram Webhook ---

@app.post("/api/telegram/webhook")
async def telegram_webhook(update: TelegramMessage):
    """Handle Telegram webhook updates."""
    if update.message:
        chat_id = update.message.get("chat", {}).get("id")
        text = update.message.get("text", "")

        if text:
            # Create task from Telegram message
            task_response = await create_task(TaskRequest(
                intent=text,
                priority="normal",
            ))

            # Log the interaction
            log_path = get_state_path("telegram_log.jsonl")
            with open(log_path, "a") as f:
                f.write(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "chat_id": chat_id,
                    "text": text,
                    "task_id": task_response.task_id,
                }) + "\n")

            return {"ok": True, "task_id": task_response.task_id}

    return {"ok": True}


# --- WebSocket for Real-time Updates ---

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates."""
    await websocket.accept()
    active_connections.append(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming messages if needed
            pass
    except WebSocketDisconnect:
        active_connections.remove(websocket)


async def broadcast_update(data: Dict[str, Any]):
    """Broadcast update to all connected clients."""
    for connection in active_connections:
        try:
            await connection.send_json(data)
        except Exception:
            pass


# --- Default UI ---

def get_default_ui() -> str:
    """Return default UI HTML."""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Autonomous Operator</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <style>
        .chat-bubble { animation: fadeIn 0.3s ease-in; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
    </style>
</head>
<body class="bg-gray-900 text-white min-h-screen">
    <div class="container mx-auto px-4 py-8 max-w-4xl">
        <header class="mb-8">
            <h1 class="text-3xl font-bold text-blue-400">Autonomous Operator</h1>
            <p class="text-gray-400">Tell me what you need. I'll figure out the rest.</p>
        </header>

        <!-- Status Bar -->
        <div id="status" class="bg-gray-800 rounded-lg p-4 mb-6 flex justify-between items-center">
            <div>
                <span class="text-green-400">●</span>
                <span class="ml-2">System Ready</span>
            </div>
            <div class="text-gray-400 text-sm">
                <span id="task-count">0</span> tasks
            </div>
        </div>

        <!-- Chat Interface -->
        <div class="bg-gray-800 rounded-lg p-4 mb-4 h-96 overflow-y-auto" id="chat-container">
            <div class="chat-bubble bg-blue-600 text-white p-3 rounded-lg mb-4 max-w-xl">
                <p>Hello! I'm your autonomous operator. Tell me what you want to accomplish, and I'll handle the details.</p>
                <p class="text-sm text-blue-200 mt-2">Try: "Scrape this website", "Monitor the API", "Deploy to staging"</p>
            </div>
        </div>

        <!-- Input -->
        <form id="task-form" class="flex gap-2 mb-8">
            <input type="text" id="intent-input"
                class="flex-1 bg-gray-700 text-white px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="What do you need handled?"
                autocomplete="off">
            <button type="submit"
                class="bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded-lg font-semibold transition">
                Send
            </button>
        </form>

        <!-- Tabs -->
        <div class="flex gap-4 mb-4 border-b border-gray-700">
            <button onclick="showTab('tasks')" class="tab-btn px-4 py-2 text-blue-400 border-b-2 border-blue-400">Tasks</button>
            <button onclick="showTab('mcps')" class="tab-btn px-4 py-2 text-gray-400 hover:text-white">MCPs</button>
            <button onclick="showTab('schedule')" class="tab-btn px-4 py-2 text-gray-400 hover:text-white">Schedule</button>
            <button onclick="showTab('settings')" class="tab-btn px-4 py-2 text-gray-400 hover:text-white">Settings</button>
        </div>

        <!-- Tab Content -->
        <div id="tab-content" class="bg-gray-800 rounded-lg p-4">
            <div id="tasks-tab">
                <h2 class="text-xl font-semibold mb-4">Task Ledger</h2>
                <div id="task-list" class="space-y-2"></div>
            </div>
            <div id="mcps-tab" class="hidden">
                <h2 class="text-xl font-semibold mb-4">Available MCPs</h2>
                <div id="mcp-list" class="grid grid-cols-2 gap-4"></div>
            </div>
            <div id="schedule-tab" class="hidden">
                <h2 class="text-xl font-semibold mb-4">Scheduled Tasks</h2>
                <div id="schedule-list" class="space-y-2"></div>
            </div>
            <div id="settings-tab" class="hidden">
                <h2 class="text-xl font-semibold mb-4">Preferences</h2>
                <form id="settings-form" class="space-y-4">
                    <div>
                        <label class="block text-gray-400 mb-2">Risk Tolerance</label>
                        <select id="risk-tolerance" class="bg-gray-700 px-4 py-2 rounded w-full">
                            <option value="low">Low - Ask before anything risky</option>
                            <option value="medium" selected>Medium - Ask for high-risk only</option>
                            <option value="high">High - Just do it</option>
                        </select>
                    </div>
                    <div>
                        <label class="flex items-center gap-2">
                            <input type="checkbox" id="auto-install" class="w-4 h-4">
                            <span>Auto-install MCPs when needed</span>
                        </label>
                    </div>
                    <button type="submit" class="bg-green-600 hover:bg-green-700 px-4 py-2 rounded">
                        Save Preferences
                    </button>
                </form>
            </div>
        </div>
    </div>

    <script>
        const API = '';
        let ws;

        // WebSocket connection
        function connectWS() {
            const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${location.host}/ws`);
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                handleUpdate(data);
            };
            ws.onclose = () => setTimeout(connectWS, 3000);
        }

        function handleUpdate(data) {
            if (data.type === 'task_created' || data.type === 'task_updated') {
                loadTasks();
            }
        }

        // Tab switching
        function showTab(tabName) {
            document.querySelectorAll('[id$="-tab"]').forEach(el => el.classList.add('hidden'));
            document.querySelectorAll('.tab-btn').forEach(el => {
                el.classList.remove('text-blue-400', 'border-b-2', 'border-blue-400');
                el.classList.add('text-gray-400');
            });
            document.getElementById(tabName + '-tab').classList.remove('hidden');
            event.target.classList.add('text-blue-400', 'border-b-2', 'border-blue-400');
            event.target.classList.remove('text-gray-400');

            if (tabName === 'tasks') loadTasks();
            if (tabName === 'mcps') loadMCPs();
            if (tabName === 'schedule') loadSchedule();
            if (tabName === 'settings') loadSettings();
        }

        // Load data
        async function loadTasks() {
            const res = await fetch(API + '/api/tasks');
            const data = await res.json();
            const list = document.getElementById('task-list');

            if (data.tasks.length === 0) {
                list.innerHTML = '<p class="text-gray-400 text-center py-8">No tasks yet. Tell me what you need above!</p>';
            } else {
                list.innerHTML = data.tasks.map(t => `
                    <div class="bg-gray-700 p-4 rounded mb-2">
                        <div class="flex items-start justify-between">
                            <div class="flex-1">
                                <div class="flex items-center gap-2 mb-1">
                                    <span class="${getStateColor(t.state)} text-lg">${getStateIcon(t.state)}</span>
                                    <span class="font-medium">${t.description}</span>
                                </div>
                                <div class="text-xs text-gray-400 ml-6">
                                    <span class="px-2 py-0.5 rounded ${getStateBadgeColor(t.state)}">${t.state}</span>
                                    ${t.blocked_reason ? `<span class="ml-2 text-red-400">${t.blocked_reason}</span>` : ''}
                                    ${t.execution_plan ? `<span class="ml-2 text-blue-400">Type: ${t.execution_plan.task_type}</span>` : ''}
                                </div>
                            </div>
                            <div class="flex gap-2 ml-4">
                                ${t.state === 'pending' ? `
                                    <button onclick="executeTask('${t.id}')" class="px-3 py-1 bg-green-600 hover:bg-green-700 rounded text-sm" title="Run this task">
                                        Run
                                    </button>
                                ` : ''}
                                ${t.state === 'in_progress' ? `
                                    <button onclick="completeTask('${t.id}')" class="px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded text-sm" title="Mark as done">
                                        Done
                                    </button>
                                ` : ''}
                                ${t.state === 'blocked' ? `
                                    <button onclick="retryTask('${t.id}')" class="px-3 py-1 bg-yellow-600 hover:bg-yellow-700 rounded text-sm" title="Retry task">
                                        Retry
                                    </button>
                                ` : ''}
                                <button onclick="deleteTask('${t.id}')" class="px-3 py-1 bg-red-600 hover:bg-red-700 rounded text-sm" title="Delete task">
                                    X
                                </button>
                            </div>
                        </div>
                    </div>
                `).join('');
            }
            document.getElementById('task-count').textContent = data.total;
        }

        function getStateIcon(state) {
            const icons = { completed: '✓', in_progress: '◐', blocked: '!', pending: '○' };
            return icons[state] || '○';
        }

        function getStateColor(state) {
            const colors = { completed: 'text-green-400', in_progress: 'text-blue-400', blocked: 'text-red-400', pending: 'text-yellow-400' };
            return colors[state] || 'text-gray-400';
        }

        function getStateBadgeColor(state) {
            const colors = { completed: 'bg-green-900 text-green-300', in_progress: 'bg-blue-900 text-blue-300', blocked: 'bg-red-900 text-red-300', pending: 'bg-yellow-900 text-yellow-300' };
            return colors[state] || 'bg-gray-600';
        }

        async function loadMCPs() {
            const res = await fetch(API + '/api/mcps');
            const data = await res.json();
            const list = document.getElementById('mcp-list');
            list.innerHTML = data.mcps.map(m => `
                <div class="bg-gray-700 p-4 rounded">
                    <div class="flex justify-between items-start mb-2">
                        <h3 class="font-semibold">${m.name}</h3>
                        <span class="${m.installed ? 'text-green-400' : 'text-gray-500'}">${m.installed ? '✓' : '○'}</span>
                    </div>
                    <p class="text-gray-400 text-sm mb-2">${m.description}</p>
                    <span class="text-xs bg-gray-600 px-2 py-1 rounded">${m.category}</span>
                    ${!m.installed ? `<button onclick="installMCP('${m.name}')" class="ml-2 text-xs bg-blue-600 px-2 py-1 rounded">Install</button>` : ''}
                </div>
            `).join('');
        }

        async function loadSchedule() {
            const res = await fetch(API + '/api/schedule');
            const data = await res.json();
            const list = document.getElementById('schedule-list');
            list.innerHTML = data.map(s => `
                <div class="flex justify-between items-center bg-gray-700 p-3 rounded">
                    <div>
                        <span class="font-semibold">${s.name}</span>
                        <span class="text-gray-400 ml-2">${s.schedule_type}</span>
                    </div>
                    <button onclick="deleteSchedule('${s.id}')" class="text-red-400 hover:text-red-300">Delete</button>
                </div>
            `).join('') || '<p class="text-gray-400">No scheduled tasks</p>';
        }

        async function loadSettings() {
            const res = await fetch(API + '/api/preferences');
            const data = await res.json();
            document.getElementById('risk-tolerance').value = data.risk_tolerance || 'medium';
            document.getElementById('auto-install').checked = data.auto_install_mcps || false;
        }

        // Actions
        async function executeTask(id) {
            const chat = document.getElementById('chat-container');
            chat.innerHTML += `<div class="chat-bubble bg-gray-600 text-white p-3 rounded-lg mb-4 max-w-xl"><em>Running task ${id}...</em></div>`;
            chat.scrollTop = chat.scrollHeight;

            const res = await fetch(API + `/api/tasks/${id}/execute`, { method: 'POST' });
            const data = await res.json();

            let message = '';
            if (data.status === 'blocked') {
                message = `<strong>Task Blocked</strong><br>${data.message}`;
            } else if (data.status === 'error') {
                message = `<strong>Error:</strong> ${data.message}`;
            } else {
                message = `<strong>Task Started</strong><br>Type: ${data.task_type}<br>`;
                if (data.steps) {
                    message += data.steps.map(s => `• ${s.action}`).join('<br>');
                }
            }

            chat.innerHTML += `<div class="chat-bubble bg-blue-600 text-white p-3 rounded-lg mb-4 max-w-xl">${message}</div>`;
            chat.scrollTop = chat.scrollHeight;
            loadTasks();
        }

        async function completeTask(id) {
            await fetch(API + `/api/tasks/${id}?state=completed`, { method: 'PUT' });
            const chat = document.getElementById('chat-container');
            chat.innerHTML += `<div class="chat-bubble bg-green-600 text-white p-3 rounded-lg mb-4 max-w-xl">Task completed!</div>`;
            chat.scrollTop = chat.scrollHeight;
            loadTasks();
        }

        async function retryTask(id) {
            // Reset to pending and try again
            await fetch(API + `/api/tasks/${id}?state=pending`, { method: 'PUT' });
            loadTasks();
            executeTask(id);
        }

        async function deleteTask(id) {
            if (!confirm('Delete this task?')) return;
            await fetch(API + `/api/tasks/${id}`, { method: 'DELETE' });
            loadTasks();
        }

        async function installMCP(name) {
            const chat = document.getElementById('chat-container');
            chat.innerHTML += `<div class="chat-bubble bg-gray-600 text-white p-3 rounded-lg mb-4 max-w-xl"><em>Installing ${name}...</em></div>`;
            chat.scrollTop = chat.scrollHeight;

            const res = await fetch(API + `/api/mcps/${name}/install`, { method: 'POST' });
            const data = await res.json();

            const message = data.success
                ? `<strong>Installed ${name}</strong>`
                : `<strong>Failed to install ${name}</strong><br><span class="text-xs">${data.error?.substring(0, 200) || 'Unknown error'}</span>`;

            chat.innerHTML += `<div class="chat-bubble ${data.success ? 'bg-green-600' : 'bg-red-600'} text-white p-3 rounded-lg mb-4 max-w-xl">${message}</div>`;
            chat.scrollTop = chat.scrollHeight;
            loadMCPs();
        }

        async function deleteSchedule(id) {
            if (!confirm('Delete this scheduled task?')) return;
            await fetch(API + `/api/schedule/${id}`, { method: 'DELETE' });
            loadSchedule();
        }

        // Form handlers
        document.getElementById('task-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const input = document.getElementById('intent-input');
            const intent = input.value.trim();
            if (!intent) return;

            // Add user message to chat
            const chat = document.getElementById('chat-container');
            chat.innerHTML += `
                <div class="chat-bubble bg-gray-600 text-white p-3 rounded-lg mb-4 max-w-xl ml-auto">
                    ${intent}
                </div>
            `;

            // Create task
            const res = await fetch(API + '/api/task', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ intent }),
            });
            const data = await res.json();

            // Add response to chat
            chat.innerHTML += `
                <div class="chat-bubble bg-blue-600 text-white p-3 rounded-lg mb-4 max-w-xl">
                    <p>Got it! I'll handle: <strong>${intent}</strong></p>
                    <p class="text-sm text-blue-200 mt-1">Task ID: ${data.task_id}</p>
                </div>
            `;

            chat.scrollTop = chat.scrollHeight;
            input.value = '';
            loadTasks();
        });

        document.getElementById('settings-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const prefs = {
                risk_tolerance: document.getElementById('risk-tolerance').value,
                auto_install_mcps: document.getElementById('auto-install').checked,
            };
            await fetch(API + '/api/preferences', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(prefs),
            });
            alert('Preferences saved!');
        });

        // Init
        connectWS();
        loadTasks();
    </script>
</body>
</html>
"""


# --- Self-Healing & System Control Endpoints ---

@app.post("/api/feedback")
async def submit_feedback(request: FeedbackRequest, background_tasks: BackgroundTasks):
    """
    Submit feedback or error report for self-healing.

    The system will use Claude Code to analyze and fix the issue.
    """
    from core.self_healing import get_self_healing

    healer = get_self_healing()

    if not healer.is_available:
        return {
            "success": False,
            "message": "Claude Code CLI not available. Self-healing requires Claude Code to be installed.",
            "status": "unavailable",
        }

    # Start the fix in the background
    async def do_fix():
        result = await healer.analyze_and_fix(
            issue_description=request.issue,
            error_logs=request.error_logs,
            affected_file=request.affected_file,
            context=request.context,
        )
        # Log the result
        add_task_log("self-heal", "INFO" if result["success"] else "ERROR", f"Self-healing: {result['message'][:200]}")
        await broadcast_update({
            "type": "self_heal_complete",
            "result": result,
        })

    background_tasks.add_task(do_fix)

    return {
        "success": True,
        "message": "Self-healing started. Claude Code is analyzing the issue...",
        "status": "in_progress",
    }


@app.post("/api/execute-command")
async def execute_command(request: CommandRequest):
    """
    Execute a terminal/PowerShell command.

    Use with caution - this runs commands on the server.
    """
    from core.self_healing import get_self_healing

    healer = get_self_healing()
    result = await healer.execute_command(request.command, request.cwd)

    return {
        "success": result["success"],
        "exit_code": result["exit_code"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
    }


@app.post("/api/claude-code")
async def call_claude_code(request: ClaudeCodeRequest, background_tasks: BackgroundTasks):
    """
    Call Claude Code directly with a prompt.

    This allows the UI to communicate with Claude Code for:
    - Complex reasoning
    - Code modifications
    - System analysis
    """
    from core.self_healing import get_self_healing

    healer = get_self_healing()

    if not healer.is_available:
        return {
            "success": False,
            "message": "Claude Code CLI not available.",
            "output": "",
        }

    # For long operations, run in background
    result = await healer._call_claude_code(request.prompt)

    return {
        "success": not result.startswith("ERROR:"),
        "output": result,
    }


@app.post("/api/restart-server")
async def restart_server():
    """
    Restart the API server.

    This will gracefully shut down and restart the server.
    """
    import sys
    import subprocess
    from pathlib import Path

    project_root = Path(__file__).parent.parent

    # Create a restart script
    restart_script = project_root / "state" / "restart.bat" if sys.platform == "win32" else project_root / "state" / "restart.sh"
    restart_script.parent.mkdir(parents=True, exist_ok=True)

    if sys.platform == "win32":
        script_content = f'''@echo off
timeout /t 2 /nobreak > nul
cd /d "{project_root}"
python -m api.server
'''
    else:
        script_content = f'''#!/bin/bash
sleep 2
cd "{project_root}"
python -m api.server
'''

    restart_script.write_text(script_content)

    if sys.platform != "win32":
        restart_script.chmod(0o755)

    # Schedule the restart
    async def do_restart():
        await asyncio.sleep(1)
        if sys.platform == "win32":
            subprocess.Popen(["cmd", "/c", str(restart_script)], creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen([str(restart_script)])
        # Exit current process
        os._exit(0)

    asyncio.create_task(do_restart())

    return {
        "success": True,
        "message": "Server restarting in 3 seconds. Refresh the page after 5 seconds.",
    }


@app.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """
    Cancel a running task.
    """
    global running_tasks

    if task_id in running_tasks:
        task = running_tasks[task_id]
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        del running_tasks[task_id]

        # Update task state
        tasks = load_json_state("tasks.json")
        for t in tasks.get("tasks", []):
            if t.get("id") == task_id:
                t["state"] = "cancelled"
                t["result"] = {"status": "cancelled", "message": "Task cancelled by user"}
                break
        save_json_state("tasks.json", tasks)

        add_task_log(task_id, "WARNING", "Task cancelled by user")

        return {"success": True, "message": "Task cancelled"}

    # Task might not be in running_tasks but still in progress
    tasks = load_json_state("tasks.json")
    for t in tasks.get("tasks", []):
        if t.get("id") == task_id:
            if t["state"] == "in_progress":
                t["state"] = "cancelled"
                t["result"] = {"status": "cancelled", "message": "Task cancelled by user"}
                save_json_state("tasks.json", tasks)
                add_task_log(task_id, "WARNING", "Task cancelled by user")
                return {"success": True, "message": "Task marked as cancelled"}

    return {"success": False, "message": "Task not found or not running"}


@app.post("/api/browse")
async def browse_with_playwright(request: TaskRequest):
    """
    Browse a website using Playwright for full browser automation.

    This is for sites that require JavaScript or complex interaction.
    """
    try:
        from skills.browser_automation import browse_with_playwright as do_browse

        # Extract URL from intent
        import re
        url_match = re.search(r'https?://[^\s]+', request.intent)
        if not url_match:
            domain_match = re.search(r'([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', request.intent)
            if domain_match:
                url = f"https://{domain_match.group(1)}"
            else:
                return {"success": False, "error": "No URL found in request"}
        else:
            url = url_match.group(0)

        # Extract search terms
        orchestrator = get_orchestrator()
        search_terms = orchestrator._extract_search_terms(request.intent)

        result = await do_browse(url, request.intent, search_terms)

        return result

    except ImportError:
        return {
            "success": False,
            "error": "Playwright not installed. Run: pip install playwright && playwright install chromium",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


# --- Run ---

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
