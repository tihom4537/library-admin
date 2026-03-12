"""
Sarvam AI speech-to-text for Kannada voice messages.

Flow:
1. Whatomate webhook arrives with message_type=audio, content=message_id
2. Download audio bytes from Whatomate: GET /api/media/{message_id}
3. POST to Sarvam STT API → get Kannada transcription
4. Pass transcription to intent classifier

TODO: Implement once Sarvam API key is available and audio format is confirmed.
The audio from WhatsApp is Opus/OGG; Sarvam may require WAV — add ffmpeg conversion if needed.
"""
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def transcribe_audio(audio_bytes: bytes, mime_type: str = "audio/ogg") -> str | None:
    """
    Transcribe Kannada audio using Sarvam AI STT API.
    Returns the transcription string, or None on failure.

    Args:
        audio_bytes: Raw audio bytes (typically Opus/OGG from WhatsApp)
        mime_type:   MIME type of the audio

    TODO:
        - Confirm Sarvam STT endpoint and request format
        - Handle audio format conversion (OGG → WAV if needed)
        - Build from scratch per roadmap Phase 3
    """
    if not settings.sarvam_api_key:
        logger.warning("SARVAM_API_KEY not set — STT is disabled")
        return None

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.sarvam_base_url}/v1/speech-to-text",
                headers={"Authorization": f"Bearer {settings.sarvam_api_key}"},
                files={"file": ("audio.ogg", audio_bytes, mime_type)},
                data={"language_code": "kn-IN", "model": "saarika:v2"},
            )
            resp.raise_for_status()
            data = resp.json()
            transcript = data.get("transcript", "")
            logger.info("STT transcription: %s", transcript[:100])
            return transcript

    except Exception as e:
        logger.error("Sarvam STT failed: %s", e)
        return None
