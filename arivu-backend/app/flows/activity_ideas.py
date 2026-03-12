"""
Flow 4: Activity Ideas

Librarian asks for activity ideas → bot queries ActivityTemplate DB
and presents up to 5 ideas as a list message.
Librarian picks one → bot sends full details (steps, materials, duration).

States:
  MAIN → (activity_ideas intent) → show idea list
  FLOW_4_BROWSING → waiting for selection
"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import ActivityTemplate
from app.session.manager import Session, session_manager
from app.whatomate.client import whatomate

logger = logging.getLogger(__name__)

# Fallback ideas used when DB has no seeded activity templates yet
FALLBACK_IDEAS = [
    {
        "id": "fallback_story_circle",
        "title": "📖 Story Circle",
        "description": "One person tells a story — others continue it.",
        "duration": "30 min",
        "materials": "Nothing needed",
        "steps": (
            "1️⃣ Seat children in a circle.\n"
            "2️⃣ Start a story — after 2-3 sentences, pass it to the next child.\n"
            "3️⃣ Each child adds a few sentences.\n"
            "4️⃣ The last child ends the story."
        ),
        "tip": "For younger children, use a familiar story as the starting point.",
    },
    {
        "id": "fallback_drawing",
        "title": "🎨 Drawing Competition",
        "description": "Give a theme — let children draw and share.",
        "duration": "45 min",
        "materials": "Paper, crayons or pencils",
        "steps": (
            "1️⃣ Announce the theme (e.g., 'My Village', 'My Favourite Animal').\n"
            "2️⃣ Give children 20-30 minutes to draw.\n"
            "3️⃣ Display all drawings on the wall or table.\n"
            "4️⃣ Let children describe their drawing to the group."
        ),
        "tip": "Any theme works — keep it open so every child can participate.",
    },
    {
        "id": "fallback_water_experiment",
        "title": "🔬 Float or Sink?",
        "description": "Science game — which objects float in water?",
        "duration": "30 min",
        "materials": "Bucket of water, small objects (stone, leaf, plastic, metal)",
        "steps": (
            "1️⃣ Fill a bucket with water.\n"
            "2️⃣ Gather small objects — stone, leaf, eraser, key, plastic cup.\n"
            "3️⃣ Ask each child to guess: will it float or sink?\n"
            "4️⃣ Drop each object in and see what happens.\n"
            "5️⃣ Discuss why some float and some sink."
        ),
        "tip": "Use objects from the library — books, pencils, rubber bands.",
    },
    {
        "id": "fallback_riddles",
        "title": "🧩 Riddle Time",
        "description": "Share riddles in turns — great for all ages.",
        "duration": "20 min",
        "materials": "Nothing needed",
        "steps": (
            "1️⃣ Ask if anyone knows a riddle.\n"
            "2️⃣ Take turns — one child asks, others guess.\n"
            "3️⃣ Librarian shares a few riddles to get started.\n"
            "4️⃣ Award a small prize (sticker or a book to borrow) for the best riddle."
        ),
        "tip": "Folk riddles in Kannada work wonderfully — children love hearing local ones.",
    },
    {
        "id": "fallback_book_talk",
        "title": "💬 Book Talk",
        "description": "Children recommend a book to each other.",
        "duration": "25 min",
        "materials": "Library books",
        "steps": (
            "1️⃣ Each child picks a book they have read (or just like the cover of).\n"
            "2️⃣ One by one, they hold it up and say one thing they liked about it.\n"
            "3️⃣ After all have shared, ask: 'Which book do you want to read next?'\n"
            "4️⃣ Let children borrow books from today's recommendations."
        ),
        "tip": "This builds speaking confidence and reading culture at the same time.",
    },
]


async def handle_activity_ideas_start(
    phone: str,
    text: str,
    session: Session,
    db: AsyncSession,
) -> None:
    """
    Entry point: show up to 5 activity ideas.
    Tries DB first; falls back to hardcoded ideas.
    """
    ideas = await _fetch_ideas(text, db)

    if not ideas:
        ideas = FALLBACK_IDEAS

    # Store idea map in session context so selection can look up details
    idea_map = {idea["id"]: idea for idea in ideas}
    await session_manager.update_context(phone, {"idea_map": idea_map})
    await session_manager.set_state(phone, "FLOW_4_BROWSING")

    # Build list message sections
    items = [
        {
            "id": idea["id"],
            "title": idea["title"][:24],
            "description": idea["description"][:72],
        }
        for idea in ideas[:5]
    ]

    await whatomate.send_list(
        session.whatomate_contact_id,
        body=(
            "Here are some activity ideas for your library:\n\n"
            "Tap an idea to see full steps and materials."
        ),
        button_text="See Ideas",
        sections=[{"title": "Activity Ideas", "rows": items}],
    )


async def handle_activity_ideas_selection(
    phone: str,
    button_id: str,
    session: Session,
    db: AsyncSession,
) -> None:
    """Librarian selected an idea — show full details."""
    idea_map = session.context.get("idea_map", {})
    idea = idea_map.get(button_id)

    if not idea:
        # ID not in session — fall back to a helpful message
        await whatomate.send_text(
            session.whatomate_contact_id,
            "I couldn't find that activity. Type 'ideas' or '4' to see the list again.",
        )
        await session_manager.set_state(phone, "MAIN")
        return

    detail = (
        f"*{idea['title']}*\n"
        f"⏱ {idea['duration']} | 📦 {idea['materials']}\n\n"
        f"*Steps:*\n{idea['steps']}\n\n"
        f"💡 *Tip:* {idea.get('tip', '')}"
    )

    await whatomate.send_text(session.whatomate_contact_id, detail)
    await whatomate.send_buttons(
        session.whatomate_contact_id,
        body="Would you like to do this activity?",
        buttons=[
            {"type": "reply", "reply": {"id": "ideas_will_do", "title": "✅ I will do this"}},
            {"type": "reply", "reply": {"id": "ideas_see_more", "title": "📋 See more ideas"}},
        ],
    )


async def handle_activity_ideas_button(
    phone: str,
    button_id: str,
    session: Session,
    db: AsyncSession,
) -> None:
    """Handle follow-up buttons after showing idea details."""
    cid = session.whatomate_contact_id

    if button_id == "ideas_will_do":
        await whatomate.send_text(
            cid,
            "Wonderful! 🎉\n\n"
            "After you conduct the activity, send a photo and I will help you record it.\n"
            "Good luck! 🍀",
        )
        await session_manager.set_state(phone, "MAIN")

    elif button_id == "ideas_see_more":
        # Re-show the list from session
        idea_map = session.context.get("idea_map", {})
        if idea_map:
            items = [
                {
                    "id": k,
                    "title": v["title"][:24],
                    "description": v["description"][:72],
                }
                for k, v in idea_map.items()
            ]
            await whatomate.send_list(
                cid,
                body="Here are all the activity ideas again:",
                button_text="See Ideas",
                sections=[{"title": "Activity Ideas", "rows": items}],
            )
        else:
            await whatomate.send_text(cid, "Type 'ideas' to get a new list of activity suggestions.")
            await session_manager.set_state(phone, "MAIN")
    else:
        await session_manager.set_state(phone, "MAIN")


# ---------------------------------------------------------------------------
# DB query
# ---------------------------------------------------------------------------

async def _fetch_ideas(query_text: str, db: AsyncSession) -> list[dict]:
    """
    Query ActivityTemplate for approved activities.
    Applies a simple keyword filter if the librarian mentioned a category.
    """
    category = _extract_category_hint(query_text)

    stmt = select(ActivityTemplate).where(ActivityTemplate.approved == True)
    if category:
        stmt = stmt.where(ActivityTemplate.category == category)
    stmt = stmt.limit(5)

    result = await db.execute(stmt)
    templates = result.scalars().all()

    if not templates:
        return []

    return [
        {
            "id": str(t.id),
            "title": t.title_en or t.title_kn,
            "description": (t.description_kn or "")[:100],
            "duration": f"{t.duration_minutes} min" if t.duration_minutes else "30 min",
            "materials": t.materials_kn or "As available",
            "steps": t.instructions_kn or "Steps to be added.",
            "tip": "",
        }
        for t in templates
    ]


def _extract_category_hint(text: str) -> str | None:
    """Simple keyword check to filter by category."""
    text_lower = text.lower()
    if any(w in text_lower for w in ["science", "experiment", "ವಿಜ್ಞಾನ"]):
        return "science"
    if any(w in text_lower for w in ["art", "draw", "paint", "ಕಲೆ"]):
        return "art"
    if any(w in text_lower for w in ["story", "read", "book", "ಕಥೆ", "ಓದು"]):
        return "reading"
    if any(w in text_lower for w in ["craft", "make", "ಕರಕುಶಲ"]):
        return "craft"
    return None
