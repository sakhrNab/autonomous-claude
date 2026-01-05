"""
Integrations Module

External integrations for the autonomous operator:
- Telegram bot for remote control
- Phone/voice integration (future)
- Slack integration (future)
- Discord integration (future)
"""

from .telegram_bot import TelegramBot

__all__ = [
    "TelegramBot",
]
