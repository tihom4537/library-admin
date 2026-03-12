"""
Sarvam AI intent classifier for Kannada text messages.

Classifies incoming text into one of these intents:
  check_activity   → "ಈ ವಾರ ಏನು ಮಾಡಬೇಕು?" / "what should I do this week?"
  report_activity  → "ನಾನು ಚಟುವಟಿಕೆ ಮಾಡಿದ್ದೇನೆ" / wants to log activity
  tech_support     → "ಕಂಪ್ಯೂಟರ್ ಆನ್ ಆಗುತ್ತಿಲ್ಲ" / computer/tech problem
  activity_ideas   → "ಬೇರೆ ಚಟುವಟಿಕೆ ತೋರಿಸಿ" / show more activity ideas
  learning         → "ಕಲಿಕೆ" / micro-learning related
  local_content    → "ನನ್ನ ಹಳ್ಳಿಯ ಕಥೆ" / sharing local stories/crafts
  greeting         → "ನಮಸ್ಕಾರ" / general greeting
  feedback         → complaint or suggestion
  unknown          → anything else

TODO: Replace stub with real Sarvam AI API call once API key is available.
API docs: https://docs.sarvam.ai/
"""
import logging
import re

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

VALID_INTENTS = {
    "check_activity",
    "report_activity",
    "tech_support",
    "activity_ideas",
    "learning",
    "local_content",
    "greeting",
    "feedback",
    "unknown",
}

# Keyword-based fallback classifier (used when Sarvam API key is not set)
KEYWORD_RULES: list[tuple[str, list[str]]] = [
    ("greeting", [
        "ನಮಸ್ಕಾರ", "namaskara", "hello", "hi", "ಹಲೋ", "ಶುಭ"
    ]),
    ("check_activity", [
        "ಏನು ಮಾಡಬೇಕು", "what to do", "activity", "ಚಟುವಟಿಕೆ", "ಈ ವಾರ",
        "ಕಾರ್ಯಕ್ರಮ", "what should i do"
    ]),
    ("report_activity", [
        "ಮಾಡಿದ್ದೇನೆ", "ಮಾಡಿದ", "report", "log", "done", "completed",
        "ಮಕ್ಕಳು ಬಂದರು", "ಚಟುವಟಿಕೆ ಮಾಡಿದ"
    ]),
    ("tech_support", [
        "ಕಂಪ್ಯೂಟರ್", "computer", "problem", "ಸಮಸ್ಯೆ", "ಆಗುತ್ತಿಲ್ಲ",
        "not working", "help", "ಸಹಾಯ", "internet", "ಇಂಟರ್ನೆಟ್", "wifi",
        "printer", "ಮೌಸ್", "keyboard"
    ]),
    ("activity_ideas", [
        "idea", "ಬೇರೆ", "ಇನ್ನೊಂದು", "ಆಯ್ಡಿಯಾ", "suggest", "ಸಲಹೆ",
        "ಮಕ್ಕಳಿಗೆ", "science", "art", "craft", "ಕಲೆ"
    ]),
    ("learning", [
        "ಕಲಿಕೆ", "learn", "training", "ತರಬೇತಿ", "module", "ಮಾಡ್ಯೂಲ್"
    ]),
    ("local_content", [
        "ಕಥೆ", "story", "ಹಾಡು", "song", "ಆಟ", "game", "local", "ಸ್ಥಳೀಯ",
        "ಗ್ರಾಮ", "village", "ಸಂಪ್ರದಾಯ", "tradition"
    ]),
    ("feedback", [
        "complaint", "ದೂರು", "suggestion", "ಸಲಹೆ", "feedback", "problem with app"
    ]),
]


def _keyword_classify(text: str) -> str:
    """Simple keyword-based classifier as fallback."""
    lower = text.lower()
    for intent, keywords in KEYWORD_RULES:
        for kw in keywords:
            if kw.lower() in lower:
                return intent
    return "unknown"


SARVAM_SYSTEM_PROMPT = """You are an intent classifier for a WhatsApp bot used by rural librarians in Karnataka.
Classify the user's message into exactly ONE of these intents:
- check_activity: wants to know what activity to do this week
- report_activity: wants to log/report a completed activity
- tech_support: computer or technology problem
- activity_ideas: wants activity ideas or alternatives
- learning: interested in micro-learning content
- local_content: wants to share local stories, songs, games, or crafts
- greeting: general greeting or pleasantry
- feedback: complaint or suggestion about the bot or library program
- unknown: anything else

Respond with ONLY the intent name, nothing else."""


async def classify_intent(text: str) -> str:
    """
    Classify the intent of a Kannada/English text message.
    Uses Sarvam AI if API key is set, otherwise falls back to keyword matching.

    Returns one of the VALID_INTENTS strings.
    """
    if not settings.sarvam_api_key:
        # TODO: Remove this fallback once SARVAM_API_KEY is configured
        logger.warning("SARVAM_API_KEY not set — using keyword-based classifier")
        return _keyword_classify(text)

    return await _sarvam_classify(text)


async def _sarvam_classify(text: str) -> str:
    """Call Sarvam AI text API for intent classification."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.sarvam_base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.sarvam_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "saarika:v2",
                    "messages": [
                        {"role": "system", "content": SARVAM_SYSTEM_PROMPT},
                        {"role": "user", "content": text},
                    ],
                    "max_tokens": 20,
                    "temperature": 0,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            raw = data["choices"][0]["message"]["content"].strip().lower()

            # Sanitise: take first word if model returned extra text
            intent = raw.split()[0] if raw else "unknown"
            if intent not in VALID_INTENTS:
                logger.warning("Sarvam returned unknown intent '%s', defaulting to 'unknown'", intent)
                return "unknown"
            return intent

    except Exception as e:
        logger.error("Sarvam intent classification failed: %s — falling back to keywords", e)
        return _keyword_classify(text)
