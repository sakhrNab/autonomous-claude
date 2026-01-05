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

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
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
async def create_task(request: TaskRequest):
    """Create a new task from user intent."""
    import uuid

    task_id = str(uuid.uuid4())[:8]

    # Load existing tasks
    tasks = load_json_state("tasks.json")
    if "tasks" not in tasks:
        tasks["tasks"] = []

    # Create new task
    new_task = {
        "id": f"task_{task_id}",
        "description": request.intent,
        "state": "pending",
        "priority": request.priority,
        "created_at": datetime.now().isoformat(),
        "scheduled_at": request.scheduled_at,
    }

    tasks["tasks"].append(new_task)
    tasks["updated_at"] = datetime.now().isoformat()
    save_json_state("tasks.json", tasks)

    # Notify WebSocket clients
    await broadcast_update({
        "type": "task_created",
        "task": new_task,
    })

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

        reg = MCPRegistry()
        server = reg.get(mcp_name)

        if not server:
            raise HTTPException(status_code=404, detail=f"Unknown MCP: {mcp_name}")

        # Run install command
        result = subprocess.run(
            server.install_command.split(),
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode == 0:
            reg.mark_installed(mcp_name)
            return {"success": True, "message": f"Installed {mcp_name}"}
        else:
            return {"success": False, "error": result.stderr}

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Installation timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
            list.innerHTML = data.tasks.map(t => `
                <div class="flex items-center justify-between bg-gray-700 p-3 rounded">
                    <div>
                        <span class="${t.state === 'completed' ? 'text-green-400' : t.state === 'blocked' ? 'text-red-400' : 'text-yellow-400'}">
                            ${t.state === 'completed' ? '✓' : t.state === 'blocked' ? '!' : '○'}
                        </span>
                        <span class="ml-2">${t.description}</span>
                    </div>
                    <span class="text-gray-400 text-sm">${t.state}</span>
                </div>
            `).join('');
            document.getElementById('task-count').textContent = data.total;
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
        async function installMCP(name) {
            const res = await fetch(API + `/api/mcps/${name}/install`, { method: 'POST' });
            const data = await res.json();
            alert(data.success ? `Installed ${name}` : `Failed: ${data.error}`);
            loadMCPs();
        }

        async function deleteSchedule(id) {
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


# --- Run ---

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
