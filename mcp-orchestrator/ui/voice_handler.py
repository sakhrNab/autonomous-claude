"""
Voice Handler

Handles voice input/output for the MCP orchestrator.

Per the guides:
- Voice button
- Voice summaries
- Speech-to-text integration
- Text-to-speech responses
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
import asyncio
import base64


@dataclass
class VoiceMessage:
    """A voice message."""
    message_id: str
    user_id: str
    direction: str  # "incoming" or "outgoing"
    audio_data: Optional[bytes]
    transcript: Optional[str]
    timestamp: datetime
    metadata: Dict[str, Any]


class VoiceHandler:
    """
    Voice Handler - Manages voice I/O.

    This handler:
    - Receives voice input
    - Converts speech to text
    - Generates voice responses
    - Manages voice session state
    """

    def __init__(
        self,
        stt_provider: str = "openai",
        tts_provider: str = "openai",
        api_key: Optional[str] = None
    ):
        self.stt_provider = stt_provider
        self.tts_provider = tts_provider
        self.api_key = api_key
        self.voice_history: List[VoiceMessage] = []
        self.active_sessions: Dict[str, Dict[str, Any]] = {}

    async def process_voice_input(
        self,
        user_id: str,
        audio_data: bytes,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process incoming voice input.

        Returns the transcribed text and any metadata.
        """
        from ..skills import SpeechToText

        message_id = f"voice_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Transcribe
        stt = SpeechToText(provider=self.stt_provider, api_key=self.api_key)
        result = await stt.execute({
            "audio_data": base64.b64encode(audio_data).decode(),
        })

        transcript = result.data.get("transcript", "") if result.success else ""

        # Record message
        message = VoiceMessage(
            message_id=message_id,
            user_id=user_id,
            direction="incoming",
            audio_data=audio_data,
            transcript=transcript,
            timestamp=datetime.now(),
            metadata={
                "session_id": session_id,
                "confidence": result.data.get("confidence", 0) if result.success else 0,
            },
        )
        self.voice_history.append(message)

        return {
            "message_id": message_id,
            "transcript": transcript,
            "success": result.success,
            "confidence": result.data.get("confidence", 0) if result.success else 0,
        }

    async def generate_voice_response(
        self,
        user_id: str,
        text: str,
        voice: str = "alloy",
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a voice response from text.

        Returns audio data and metadata.
        """
        from ..skills import TextToSpeech

        message_id = f"voice_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Generate speech
        tts = TextToSpeech(provider=self.tts_provider, api_key=self.api_key)
        result = await tts.execute({
            "text": text,
            "voice": voice,
        })

        audio_data = None
        if result.success and result.data.get("audio_data"):
            audio_data = base64.b64decode(result.data["audio_data"])

        # Record message
        message = VoiceMessage(
            message_id=message_id,
            user_id=user_id,
            direction="outgoing",
            audio_data=audio_data,
            transcript=text,
            timestamp=datetime.now(),
            metadata={
                "session_id": session_id,
                "voice": voice,
            },
        )
        self.voice_history.append(message)

        return {
            "message_id": message_id,
            "audio_data": result.data.get("audio_data") if result.success else None,
            "text": text,
            "success": result.success,
            "duration_seconds": result.data.get("duration_seconds", 0) if result.success else 0,
        }

    def start_voice_session(self, user_id: str) -> str:
        """Start a new voice session."""
        session_id = f"voice_session_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.active_sessions[session_id] = {
            "session_id": session_id,
            "user_id": user_id,
            "started_at": datetime.now().isoformat(),
            "messages": [],
        }
        return session_id

    def end_voice_session(self, session_id: str) -> Dict[str, Any]:
        """End a voice session."""
        session = self.active_sessions.pop(session_id, None)
        if session:
            session["ended_at"] = datetime.now().isoformat()
            return session
        return {}

    def get_voice_history(
        self,
        user_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get voice message history."""
        messages = self.voice_history
        if user_id:
            messages = [m for m in messages if m.user_id == user_id]

        return [
            {
                "message_id": m.message_id,
                "direction": m.direction,
                "transcript": m.transcript,
                "timestamp": m.timestamp.isoformat(),
            }
            for m in messages[-limit:]
        ]

    async def generate_summary_voice(
        self,
        result: Dict[str, Any],
        user_id: str
    ) -> Dict[str, Any]:
        """
        Generate a voice summary of workflow results.
        """
        # Create summary text
        if result.get("success"):
            summary = "Your request has been completed successfully. "
            if result.get("result"):
                iterations = result["result"].get("iterations", 0)
                elapsed = result["result"].get("elapsed_seconds", 0)
                if iterations:
                    summary += f"It took {iterations} steps. "
                if elapsed:
                    if elapsed < 60:
                        summary += f"Total time was {elapsed:.0f} seconds."
                    else:
                        summary += f"Total time was {elapsed/60:.1f} minutes."
        else:
            summary = f"Sorry, there was an error: {result.get('error', 'Unknown error')}"

        return await self.generate_voice_response(user_id, summary)
