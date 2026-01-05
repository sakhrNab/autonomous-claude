"""
Send Notification Skill

Sends notifications via various channels.
"""

from typing import Any, Dict, List, Optional
import httpx

from .base_skill import BaseSkill, SkillResult


class SendNotification(BaseSkill):
    """
    Skill to send notifications.

    Supports:
    - Slack
    - Email
    - SMS (via Twilio)
    - Webhooks
    - In-app notifications
    """

    name = "send_notification"
    description = "Send a notification via Slack, email, or other channels"
    required_permissions = ["notification:send"]
    estimated_cost = 0.01

    def __init__(
        self,
        slack_webhook: Optional[str] = None,
        email_api_key: Optional[str] = None
    ):
        super().__init__()
        self.slack_webhook = slack_webhook
        self.email_api_key = email_api_key

    async def execute(
        self,
        args: Dict[str, Any],
        context: Optional[Any] = None
    ) -> SkillResult:
        """
        Send a notification.

        Args:
            args:
                - channel: Notification channel (slack, email, sms, webhook)
                - recipient: Who to notify
                - message: Message content
                - title: Optional title
                - priority: low, normal, high, urgent
        """
        await self.pre_execute(args)

        channel = args.get("channel", "slack")
        recipient = args.get("recipient")
        message = args.get("message")
        title = args.get("title")
        priority = args.get("priority", "normal")

        if not message:
            return SkillResult(
                success=False,
                error="message is required",
            )

        try:
            if channel == "slack":
                result = await self._send_slack(recipient, message, title, priority)
            elif channel == "email":
                result = await self._send_email(recipient, message, title, priority)
            elif channel == "sms":
                result = await self._send_sms(recipient, message, priority)
            elif channel == "webhook":
                result = await self._send_webhook(recipient, message, title)
            else:
                result = await self._send_default(recipient, message, title)

            skill_result = SkillResult(
                success=True,
                data={
                    "channel": channel,
                    "recipient": recipient,
                    "sent": True,
                    "notification_id": result.get("id"),
                },
                cost=self.estimated_cost,
            )

        except Exception as e:
            skill_result = SkillResult(
                success=False,
                error=str(e),
            )

        await self.post_execute(skill_result)
        return skill_result

    async def _send_slack(
        self,
        recipient: str,
        message: str,
        title: Optional[str],
        priority: str
    ) -> Dict[str, Any]:
        """Send Slack notification."""
        if not self.slack_webhook:
            raise ValueError("Slack webhook not configured")

        # Format message for Slack
        emoji = {
            "low": ":information_source:",
            "normal": ":white_check_mark:",
            "high": ":warning:",
            "urgent": ":rotating_light:",
        }.get(priority, "")

        payload = {
            "text": f"{emoji} {title or 'Notification'}\n{message}",
            "channel": recipient if recipient.startswith("#") else None,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.slack_webhook,
                json=payload,
                timeout=10.0,
            )
            response.raise_for_status()

        return {"id": "slack-001", "sent": True}

    async def _send_email(
        self,
        recipient: str,
        message: str,
        title: Optional[str],
        priority: str
    ) -> Dict[str, Any]:
        """Send email notification."""
        # Placeholder for email API integration
        return {"id": "email-001", "sent": True}

    async def _send_sms(
        self,
        recipient: str,
        message: str,
        priority: str
    ) -> Dict[str, Any]:
        """Send SMS notification."""
        # Placeholder for SMS API integration (Twilio)
        return {"id": "sms-001", "sent": True}

    async def _send_webhook(
        self,
        url: str,
        message: str,
        title: Optional[str]
    ) -> Dict[str, Any]:
        """Send webhook notification."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json={"title": title, "message": message},
                timeout=10.0,
            )
            response.raise_for_status()

        return {"id": "webhook-001", "sent": True}

    async def _send_default(
        self,
        recipient: str,
        message: str,
        title: Optional[str]
    ) -> Dict[str, Any]:
        """Send to default channel (logging)."""
        return {"id": "log-001", "sent": True, "logged": True}

    def validate_args(self, args: Dict[str, Any]) -> List[str]:
        errors = []
        if not args.get("message"):
            errors.append("message is required")
        return errors

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "channel": {
                    "type": "string",
                    "enum": ["slack", "email", "sms", "webhook", "default"],
                    "description": "Notification channel",
                },
                "recipient": {
                    "type": "string",
                    "description": "Recipient (channel, email, phone, URL)",
                },
                "message": {
                    "type": "string",
                    "description": "Message content",
                },
                "title": {
                    "type": "string",
                    "description": "Optional title",
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "normal", "high", "urgent"],
                    "description": "Priority level",
                },
            },
            "required": ["message"],
        }
