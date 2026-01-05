"""
Telegram Bot Integration

Enables remote control of the autonomous operator via Telegram.

Features:
1. Send tasks via chat
2. Receive status updates
3. Voice message support (transcription → task)
4. Inline buttons for quick actions
5. Notifications for task completion/errors

Setup:
1. Create bot via @BotFather
2. Set TELEGRAM_BOT_TOKEN environment variable
3. Set webhook URL or run in polling mode
"""

import asyncio
import json
import os
import httpx
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass


@dataclass
class TelegramUser:
    """A Telegram user."""
    id: int
    username: Optional[str]
    first_name: str
    is_admin: bool = False


@dataclass
class TelegramMessage:
    """An incoming Telegram message."""
    message_id: int
    chat_id: int
    user: TelegramUser
    text: Optional[str]
    voice: Optional[Dict[str, Any]]
    reply_to: Optional[int]
    timestamp: datetime


class TelegramBot:
    """
    Telegram bot for the autonomous operator.

    Commands:
    /start - Initialize and show help
    /status - Get system status
    /tasks - List current tasks
    /mcps - List installed MCPs
    /schedule - Show scheduled tasks
    /settings - Configure preferences

    Any other message is treated as a task intent.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        api_base: str = "http://localhost:8000",
        admin_ids: Optional[List[int]] = None,
    ):
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.api_base = api_base
        self.admin_ids = set(admin_ids or [])
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.client = httpx.AsyncClient(timeout=30.0)
        self.state_path = Path("state/telegram_state.json")
        self.authorized_users: set = set()
        self._load_state()

    def _load_state(self):
        """Load bot state."""
        if self.state_path.exists():
            try:
                data = json.loads(self.state_path.read_text(encoding="utf-8"))
                self.authorized_users = set(data.get("authorized_users", []))
            except Exception:
                pass

    def _save_state(self):
        """Save bot state."""
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "authorized_users": list(self.authorized_users),
            "updated_at": datetime.now().isoformat(),
        }
        self.state_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_to: Optional[int] = None,
        keyboard: Optional[List[List[Dict]]] = None,
    ) -> Dict[str, Any]:
        """Send a message to a chat."""
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }

        if reply_to:
            payload["reply_to_message_id"] = reply_to

        if keyboard:
            payload["reply_markup"] = {
                "inline_keyboard": keyboard,
            }

        response = await self.client.post(
            f"{self.base_url}/sendMessage",
            json=payload,
        )
        return response.json()

    async def get_updates(self, offset: int = 0) -> List[Dict[str, Any]]:
        """Get updates from Telegram (polling mode)."""
        response = await self.client.get(
            f"{self.base_url}/getUpdates",
            params={"offset": offset, "timeout": 30},
        )
        data = response.json()
        return data.get("result", [])

    async def set_webhook(self, url: str) -> bool:
        """Set webhook URL for incoming updates."""
        response = await self.client.post(
            f"{self.base_url}/setWebhook",
            json={"url": url},
        )
        return response.json().get("ok", False)

    async def handle_update(self, update: Dict[str, Any]):
        """Handle an incoming update."""
        message = update.get("message")
        callback = update.get("callback_query")

        if message:
            await self._handle_message(message)
        elif callback:
            await self._handle_callback(callback)

    async def _handle_message(self, message: Dict[str, Any]):
        """Handle an incoming message."""
        chat_id = message.get("chat", {}).get("id")
        user_id = message.get("from", {}).get("id")
        username = message.get("from", {}).get("username", "")
        first_name = message.get("from", {}).get("first_name", "User")
        text = message.get("text", "")
        voice = message.get("voice")

        # Check authorization
        is_admin = user_id in self.admin_ids
        is_authorized = user_id in self.authorized_users or is_admin

        # Handle voice messages
        if voice:
            await self._handle_voice(chat_id, voice, user_id)
            return

        # Handle commands
        if text.startswith("/"):
            await self._handle_command(chat_id, text, user_id, is_admin, is_authorized)
            return

        # Require authorization for tasks
        if not is_authorized:
            await self.send_message(
                chat_id,
                "⚠️ You're not authorized. Ask an admin to run `/authorize @{}`".format(username),
            )
            return

        # Treat as task intent
        await self._create_task(chat_id, text, user_id)

    async def _handle_command(
        self,
        chat_id: int,
        text: str,
        user_id: int,
        is_admin: bool,
        is_authorized: bool,
    ):
        """Handle a command."""
        parts = text.split(maxsplit=1)
        command = parts[0].lower().replace("@", " ").split()[0]
        args = parts[1] if len(parts) > 1 else ""

        if command == "/start":
            await self._cmd_start(chat_id, user_id)
        elif command == "/status":
            await self._cmd_status(chat_id)
        elif command == "/tasks":
            await self._cmd_tasks(chat_id)
        elif command == "/mcps":
            await self._cmd_mcps(chat_id)
        elif command == "/schedule":
            await self._cmd_schedule(chat_id)
        elif command == "/settings":
            await self._cmd_settings(chat_id, args)
        elif command == "/authorize" and is_admin:
            await self._cmd_authorize(chat_id, args)
        elif command == "/help":
            await self._cmd_help(chat_id)
        else:
            await self.send_message(chat_id, "Unknown command. Try /help")

    async def _cmd_start(self, chat_id: int, user_id: int):
        """Handle /start command."""
        msg = """
👋 *Welcome to Autonomous Operator*

I'm your trusted autonomous operator. Tell me what you need, and I'll figure out the rest.

*How to use:*
Just send me what you want done:
• "Scrape the product prices from example.com"
• "Monitor the API for errors"
• "Deploy to staging"
• "Check the database status"

*Commands:*
/status - System status
/tasks - View task ledger
/mcps - Available MCPs
/schedule - Scheduled tasks
/help - More info

_You can also send voice messages!_
"""
        keyboard = [
            [
                {"text": "📊 Status", "callback_data": "status"},
                {"text": "📋 Tasks", "callback_data": "tasks"},
            ],
            [
                {"text": "🔧 MCPs", "callback_data": "mcps"},
                {"text": "⏰ Schedule", "callback_data": "schedule"},
            ],
        ]
        await self.send_message(chat_id, msg, keyboard=keyboard)

    async def _cmd_status(self, chat_id: int):
        """Handle /status command."""
        try:
            response = await self.client.get(f"{self.api_base}/api/status")
            data = response.json()

            msg = f"""
📊 *System Status*

Status: {'🟢 Running' if data.get('status') == 'running' else '🔴 Stopped'}

*Tasks:*
• Total: {data.get('tasks', {}).get('total', 0)}
• Completed: {data.get('tasks', {}).get('completed', 0)}
• Pending: {data.get('tasks', {}).get('pending', 0)}

*MCPs Installed:* {data.get('mcps_installed', 0)}

_Last updated: {data.get('last_updated', 'Unknown')}_
"""
            await self.send_message(chat_id, msg)
        except Exception as e:
            await self.send_message(chat_id, f"❌ Error: {str(e)}")

    async def _cmd_tasks(self, chat_id: int):
        """Handle /tasks command."""
        try:
            response = await self.client.get(f"{self.api_base}/api/tasks?limit=10")
            data = response.json()
            tasks = data.get("tasks", [])

            if not tasks:
                await self.send_message(chat_id, "📋 No tasks yet. Send me something to do!")
                return

            msg = "📋 *Recent Tasks*\n\n"
            for task in tasks[-10:]:
                status_emoji = {
                    "completed": "✅",
                    "pending": "⏳",
                    "in_progress": "🔄",
                    "blocked": "❌",
                }.get(task.get("state", "pending"), "⏳")

                desc = task.get("description", "")[:50]
                msg += f"{status_emoji} {desc}\n"

            msg += f"\n_Total: {data.get('total', 0)} tasks_"
            await self.send_message(chat_id, msg)
        except Exception as e:
            await self.send_message(chat_id, f"❌ Error: {str(e)}")

    async def _cmd_mcps(self, chat_id: int):
        """Handle /mcps command."""
        try:
            response = await self.client.get(f"{self.api_base}/api/mcps")
            data = response.json()
            mcps = data.get("mcps", [])

            installed = [m for m in mcps if m.get("installed")]
            available = [m for m in mcps if not m.get("installed")][:5]

            msg = "🔧 *MCP Servers*\n\n"
            msg += f"*Installed ({len(installed)}):*\n"
            for mcp in installed[:10]:
                msg += f"• {mcp.get('name')}\n"

            if available:
                msg += f"\n*Available to install:*\n"
                for mcp in available:
                    msg += f"• {mcp.get('name')} - {mcp.get('description', '')[:40]}...\n"

            await self.send_message(chat_id, msg)
        except Exception as e:
            await self.send_message(chat_id, f"❌ Error: {str(e)}")

    async def _cmd_schedule(self, chat_id: int):
        """Handle /schedule command."""
        try:
            response = await self.client.get(f"{self.api_base}/api/schedule")
            data = response.json()

            if not data:
                await self.send_message(chat_id, "⏰ No scheduled tasks. Create one via the web UI.")
                return

            msg = "⏰ *Scheduled Tasks*\n\n"
            for task in data[:10]:
                msg += f"• *{task.get('name')}*\n"
                msg += f"  Schedule: {task.get('schedule_type')}\n"

            await self.send_message(chat_id, msg)
        except Exception as e:
            await self.send_message(chat_id, f"❌ Error: {str(e)}")

    async def _cmd_settings(self, chat_id: int, args: str):
        """Handle /settings command."""
        msg = """
⚙️ *Settings*

Use the web UI to configure:
• Risk tolerance
• Auto-install MCPs
• Notification preferences

_Coming soon: inline settings_
"""
        await self.send_message(chat_id, msg)

    async def _cmd_authorize(self, chat_id: int, args: str):
        """Handle /authorize command (admin only)."""
        # Parse user ID or username from args
        if args.startswith("@"):
            await self.send_message(
                chat_id,
                "Please have the user send any message first, then authorize by their user ID.",
            )
            return

        try:
            user_id = int(args.strip())
            self.authorized_users.add(user_id)
            self._save_state()
            await self.send_message(chat_id, f"✅ User {user_id} authorized!")
        except ValueError:
            await self.send_message(chat_id, "Usage: /authorize <user_id>")

    async def _cmd_help(self, chat_id: int):
        """Handle /help command."""
        msg = """
ℹ️ *Help*

*How it works:*
1. Send me a task in natural language
2. I'll figure out which MCPs and workflows to use
3. Execute autonomously
4. Report back when done

*Examples:*
• "Scrape the headlines from news.ycombinator.com"
• "Query the database for active users"
• "Deploy the latest version to staging"
• "Monitor the API and alert if errors > 1%"

*Tips:*
• Be specific about what you want
• I'll ask if I'm unsure
• Check /status for progress

_Voice messages work too!_
"""
        await self.send_message(chat_id, msg)

    async def _create_task(self, chat_id: int, intent: str, user_id: int):
        """Create a task from user intent."""
        try:
            # First, analyze the intent
            match_response = await self.client.get(
                f"{self.api_base}/api/mcps/match",
                params={"intent": intent},
            )
            match_data = match_response.json()

            # Check for missing MCPs
            missing = match_data.get("missing_mcps", [])
            if missing:
                mcp_names = ", ".join(m.get("name") for m in missing)
                await self.send_message(
                    chat_id,
                    f"⚠️ This requires MCPs that aren't installed: *{mcp_names}*\n\n"
                    f"Installing automatically...",
                )

            # Create the task
            response = await self.client.post(
                f"{self.api_base}/api/task",
                json={"intent": intent},
            )
            data = response.json()

            task_type = match_data.get("task_type", "general")
            confidence = match_data.get("confidence", 0)

            msg = f"""
✅ *Task Created*

_{intent}_

*Type:* {task_type}
*Confidence:* {int(confidence * 100)}%
*Task ID:* `{data.get('task_id')}`

_I'll handle this and update you when done._
"""
            await self.send_message(chat_id, msg)

            # Log the task
            self._log_task(chat_id, user_id, intent, data.get("task_id"))

        except Exception as e:
            await self.send_message(chat_id, f"❌ Error creating task: {str(e)}")

    async def _handle_voice(self, chat_id: int, voice: Dict, user_id: int):
        """Handle voice message (would need speech-to-text integration)."""
        await self.send_message(
            chat_id,
            "🎤 Voice messages require speech-to-text integration.\n"
            "For now, please type your request.",
        )

    async def _handle_callback(self, callback: Dict[str, Any]):
        """Handle callback query from inline buttons."""
        chat_id = callback.get("message", {}).get("chat", {}).get("id")
        data = callback.get("data", "")

        if data == "status":
            await self._cmd_status(chat_id)
        elif data == "tasks":
            await self._cmd_tasks(chat_id)
        elif data == "mcps":
            await self._cmd_mcps(chat_id)
        elif data == "schedule":
            await self._cmd_schedule(chat_id)

    def _log_task(self, chat_id: int, user_id: int, intent: str, task_id: str):
        """Log task creation."""
        log_path = Path("state/telegram_tasks.jsonl")
        log_path.parent.mkdir(parents=True, exist_ok=True)

        entry = {
            "timestamp": datetime.now().isoformat(),
            "chat_id": chat_id,
            "user_id": user_id,
            "intent": intent,
            "task_id": task_id,
        }

        with open(log_path, "a", encoding="utf-8") as f:
            json.dump(entry, f)
            f.write("\n")

    async def notify(self, chat_id: int, message: str):
        """Send a notification to a chat."""
        await self.send_message(chat_id, f"🔔 {message}")

    async def run_polling(self):
        """Run the bot in polling mode."""
        print("Starting Telegram bot in polling mode...")
        offset = 0

        while True:
            try:
                updates = await self.get_updates(offset)
                for update in updates:
                    offset = update.get("update_id", 0) + 1
                    await self.handle_update(update)
            except Exception as e:
                print(f"Error in polling loop: {e}")
                await asyncio.sleep(5)


# Run as script
if __name__ == "__main__":
    bot = TelegramBot()
    asyncio.run(bot.run_polling())
