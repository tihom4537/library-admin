"""
Gemini AI client for admin portal features.
Uses google-genai SDK (v1 API) with gemini-2.5-flash.

- simplify_circular: paste raw Kannada circular → simplified text + action items
- suggest_activity: AI-generated activity template from category/age/season context
- generate_weekly_nudge: Monday activity or Thursday motivational nudge draft
- breakdown_pdf_content: convert any text into a 3-step micro-learning module
"""
import json
import logging

from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger(__name__)

# Lazy-init async client
_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def _model() -> str:
    return settings.gemini_model


def _extract_json(text: str) -> dict:
    """Strip markdown code fences if present, then parse JSON."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        stripped = "\n".join(lines[1:-1]).strip()
    return json.loads(stripped)


async def simplify_circular(original_text: str) -> dict:
    """
    Given raw department circular text (Kannada/English), return:
    {
      "simplified_kn": "• point1\\n• point2",
      "action_items": [{"title_kn": "...", "due_date": "YYYY-MM-DD or null"}]
    }
    """
    prompt = f"""You are helping Karnataka government librarians understand department circulars.
Given the following circular text, do two things:
1. Write a SIMPLIFIED KANNADA summary (3–5 short bullet points, plain language, easy for rural librarians).
2. Extract ACTION ITEMS — specific tasks the librarian must do, each with a due date if mentioned.

Return ONLY valid JSON in this exact format (no markdown, no extra text):
{{
  "simplified_kn": "• point1\\n• point2\\n• point3",
  "action_items": [
    {{"title_kn": "task description in Kannada", "due_date": "YYYY-MM-DD or null"}}
  ]
}}

Circular text:
{original_text}
"""
    try:
        client = _get_client()
        response = await client.aio.models.generate_content(
            model=_model(),
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.3),
        )
        return _extract_json(response.text)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Gemini simplify_circular parse error: %s", e)
        return {"simplified_kn": original_text[:500], "action_items": []}
    except Exception as e:
        logger.error("Gemini simplify_circular error: %s", e)
        raise


async def generate_weekly_nudge(
    nudge_type: str,
    week_start_date: str,
    recent_activities: list[str] | None = None,
) -> dict:
    """
    Generate a weekly nudge draft for librarians.
    nudge_type: 'monday_activity' | 'thursday_motivational'
    week_start_date: ISO date string (Monday of the target week)
    Returns: {"content_kn": str, "content_en": str}
    """
    recent_str = ", ".join(recent_activities) if recent_activities else "none"

    if nudge_type == "monday_activity":
        prompt = f"""You are helping rural Karnataka library coordinators motivate librarians.
Write a SHORT Monday morning WhatsApp nudge for the week of {week_start_date}.
The message should suggest a specific, simple library activity for that week.
Recently done activities (avoid repeating): {recent_str}

Return ONLY valid JSON:
{{
  "content_kn": "short motivational activity suggestion in Kannada (2-3 sentences, WhatsApp-friendly)",
  "content_en": "same message in English"
}}

Rules:
- Friendly, encouraging tone
- Suggest a specific activity (e.g., story time, craft, reading game)
- Keep it under 200 characters per language
- No markdown, no emojis in content
"""
    else:  # thursday_motivational
        prompt = f"""You are helping rural Karnataka library coordinators motivate librarians.
Write a SHORT Thursday motivational WhatsApp message for the week of {week_start_date}.
The message should celebrate their work and remind them of their impact on children.

Return ONLY valid JSON:
{{
  "content_kn": "short motivational message in Kannada (2-3 sentences, WhatsApp-friendly)",
  "content_en": "same message in English"
}}

Rules:
- Warm, personal, appreciative tone
- Mention children's learning impact
- Keep it under 200 characters per language
- No markdown, no emojis in content
"""
    try:
        client = _get_client()
        response = await client.aio.models.generate_content(
            model=_model(),
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.8),
        )
        return _extract_json(response.text)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Gemini generate_weekly_nudge parse error: %s", e)
        raise ValueError(f"AI returned unparseable response: {e}") from e
    except Exception as e:
        logger.error("Gemini generate_weekly_nudge error: %s", e)
        raise


async def suggest_activity(
    category: str,
    age_group: str,
    season: str | None = None,
    recent_titles: list[str] | None = None,
) -> dict:
    """
    Generate a new activity template suggestion.
    Returns a dict with title_kn, title_en, steps[], materials_kn, etc.
    """
    recent_str = ", ".join(recent_titles) if recent_titles else "none"
    season_str = season or "any season"

    prompt = f"""You are designing library activities for rural Karnataka children.
Create ONE new activity template with these parameters:
- Category: {category}
- Age group: {age_group}
- Season/context: {season_str}
- Already done recently (avoid repeating): {recent_str}

Return ONLY valid JSON (no markdown):
{{
  "title_kn": "activity title in Kannada",
  "title_en": "activity title in English",
  "description_kn": "1-2 sentence description in Kannada",
  "steps": [
    {{"order": 1, "text_kn": "step in Kannada", "text_en": "step in English"}},
    {{"order": 2, "text_kn": "...", "text_en": "..."}}
  ],
  "materials_kn": "comma-separated materials in Kannada",
  "duration_minutes": 30,
  "difficulty": "easy"
}}

Rules:
- 3–6 steps maximum
- Materials must be available in rural Karnataka (no expensive items)
- Steps must be simple enough for a librarian with basic training
- Duration 20–60 minutes
"""
    try:
        client = _get_client()
        response = await client.aio.models.generate_content(
            model=_model(),
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.7),
        )
        return _extract_json(response.text)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Gemini suggest_activity parse error: %s", e)
        raise ValueError(f"AI returned unparseable response: {e}") from e
    except Exception as e:
        logger.error("Gemini suggest_activity error: %s", e)
        raise


async def suggest_activities_for_occasion(
    occasion: str,
    occasion_date: str,
    count: int = 4,
) -> list[dict]:
    """
    Generate multiple activity suggestions themed around a special occasion.
    Returns a list of activity template dicts (NOT saved to DB).

    occasion: e.g. "International Women's Day", "Children's Day"
    occasion_date: ISO date string
    count: number of suggestions (default 4)
    """
    prompt = f"""You are designing library activities for rural Karnataka children.
The special occasion is: {occasion} on {occasion_date}

Generate exactly {count} DIFFERENT activity ideas suitable for this occasion in a rural Karnataka library.

Return ONLY a valid JSON array (no markdown, no extra text):
[
  {{
    "title_kn": "activity title in Kannada",
    "title_en": "activity title in English",
    "description_kn": "1-2 sentence description in Kannada explaining what and why",
    "category": "reading|art|science|craft|story|digital|outdoor",
    "age_group": "all|5-8|8-12|12+",
    "difficulty": "easy|medium|hard",
    "duration_minutes": 30,
    "steps_kn": [
      {{"order": 1, "text_kn": "step in Kannada", "text_en": "step in English"}},
      {{"order": 2, "text_kn": "...", "text_en": "..."}}
    ],
    "materials_kn": "comma-separated materials in Kannada"
  }}
]

Rules:
- Make each activity DIFFERENT from each other (vary category and approach)
- Theme all activities around: {occasion}
- Materials must be available in rural Karnataka (paper, crayons, storybooks — no expensive items)
- Each activity: 3-5 steps
- Duration: 20-60 minutes
- Suitable for a government library with basic resources
"""
    try:
        client = _get_client()
        response = await client.aio.models.generate_content(
            model=_model(),
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.8),
        )
        result = _extract_json(response.text)
        if isinstance(result, list):
            return result
        return []
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Gemini suggest_activities_for_occasion parse error: %s", e)
        raise ValueError(f"AI returned unparseable response: {e}") from e
    except Exception as e:
        logger.error("Gemini suggest_activities_for_occasion error: %s", e)
        raise


async def breakdown_pdf_content(text: str, topic: str | None = None) -> dict:
    """
    Convert any text content (PDF paste, notes, instructions) into a
    3-step micro-learning module for rural Karnataka librarians.

    Returns:
    {
      "title_kn": str,
      "step_one_heading_kn": str, "step_one_text_kn": str,
      "step_two_heading_kn": str, "step_two_text_kn": str,
      "step_three_heading_kn": str, "step_three_text_kn": str,
      "practice_prompt_kn": str,
      "estimated_minutes": int,
      "category": str
    }
    """
    topic_str = topic or "library skill"
    prompt = f"""You are creating a micro-learning lesson for rural Karnataka library workers.
Convert the following content into a simple 3-step WhatsApp micro-learning module.
Topic context: {topic_str}

Rules:
- All content must be in simple, clear KANNADA (ಕನ್ನಡ)
- Each step must be short (2-3 sentences max) — for WhatsApp reading
- Practice prompt must be one simple task the librarian can do today
- estimated_minutes: 3-10 (how long to read and practice)
- category: one of: computer | library | reading | craft | other

Return ONLY valid JSON (no markdown):
{{
  "title_kn": "module title in Kannada",
  "step_one_heading_kn": "Step 1 heading",
  "step_one_text_kn": "Step 1 content in Kannada",
  "step_two_heading_kn": "Step 2 heading",
  "step_two_text_kn": "Step 2 content in Kannada",
  "step_three_heading_kn": "Step 3 heading",
  "step_three_text_kn": "Step 3 content in Kannada",
  "practice_prompt_kn": "One practice task in Kannada",
  "estimated_minutes": 5,
  "category": "library"
}}

Source content:
{text[:3000]}
"""
    try:
        client = _get_client()
        response = await client.aio.models.generate_content(
            model=_model(),
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.4),
        )
        return _extract_json(response.text)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Gemini breakdown_pdf_content parse error: %s", e)
        raise ValueError(f"AI returned unparseable response: {e}") from e
    except Exception as e:
        logger.error("Gemini breakdown_pdf_content error: %s", e)
        raise
