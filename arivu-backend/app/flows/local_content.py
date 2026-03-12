"""
Flow 6: Local Content Submission

Librarian shares a local story, song, game, or craft from their village.

States:
  MAIN → (local_content intent) → show type selector buttons
  FLOW_6_AWAITING_TYPE → waiting for content type selection
  FLOW_6_AWAITING_CONTENT → waiting for voice note or photo

Button IDs:
  lc_story | lc_song | lc_game | lc_craft | lc_other
"""
import logging
import uuid as _uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.librarian import Librarian
from app.models.support import LocalContent
from app.session.manager import Session, session_manager
from app.whatomate.client import whatomate

logger = logging.getLogger(__name__)

CONTENT_TYPE_LABELS = {
    "lc_story": ("story", "Story"),
    "lc_song": ("song", "Song"),
    "lc_game": ("game", "Game"),
    "lc_craft": ("craft", "Craft"),
    "lc_other": ("other", "Other"),
}

TYPE_BUTTONS = [
    {"type": "reply", "reply": {"id": "lc_story", "title": "📖 Story"}},
    {"type": "reply", "reply": {"id": "lc_song", "title": "🎵 Song"}},
    {"type": "reply", "reply": {"id": "lc_game", "title": "🎮 Game"}},
]
TYPE_BUTTONS_2 = [
    {"type": "reply", "reply": {"id": "lc_craft", "title": "🎨 Craft"}},
    {"type": "reply", "reply": {"id": "lc_other", "title": "✨ Other"}},
]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def handle_local_content_start(phone: str, session: Session) -> None:
    """Show content type selector."""
    await session_manager.set_state(phone, "FLOW_6_AWAITING_TYPE")
    await whatomate.send_buttons(
        session.whatomate_contact_id,
        body=(
            "Wonderful! 🎉 Please share something from your village or community.\n\n"
            "What type of content would you like to share?"
        ),
        buttons=TYPE_BUTTONS,
    )
    await whatomate.send_buttons(
        session.whatomate_contact_id,
        body="More options:",
        buttons=TYPE_BUTTONS_2,
    )


# ---------------------------------------------------------------------------
# Button handler
# ---------------------------------------------------------------------------

async def handle_local_content_button(
    phone: str,
    button_id: str,
    session: Session,
    db: AsyncSession,
) -> None:
    """Route button presses within the local content flow."""
    state = session.state
    cid = session.whatomate_contact_id

    # ── Content type selected ─────────────────────────────────────────────────
    if button_id in CONTENT_TYPE_LABELS and state == "FLOW_6_AWAITING_TYPE":
        content_type, label = CONTENT_TYPE_LABELS[button_id]
        await session_manager.update_context(phone, {"content_type": content_type, "label": label})
        await session_manager.set_state(phone, "FLOW_6_AWAITING_CONTENT")

        await whatomate.send_text(
            cid,
            f"Great! Please share your *{label}*.\n\n"
            "You can:\n"
            "🎤 Send a *voice note* — tell it in your own words\n"
            "📸 Send a *photo* — if it is written or drawn\n"
            "✍️ Or just *type it* here\n\n"
            "Take your time — there is no rush! 😊",
        )
        return

    # Unknown button in this flow
    await whatomate.send_text(cid, "Please select a content type from the options above.")


# ---------------------------------------------------------------------------
# Voice note received while in local content flow
# ---------------------------------------------------------------------------

async def handle_local_content_audio(
    phone: str,
    message_id: str,
    session: Session,
    db: AsyncSession,
) -> None:
    """Librarian sent a voice note as their local content."""
    content_type = session.context.get("content_type", "other")
    label = session.context.get("label", "Content")

    entry = await _save_local_content(
        phone, session, content_type, db,
        voice_note_url=f"whatomate_media:{message_id}",
    )

    await whatomate.send_text(
        session.whatomate_contact_id,
        f"🙏 Thank you! Your *{label}* has been received.\n\n"
        "We will listen to it, review it, and share it with all libraries if it's a good fit!\n\n"
        "Your contribution helps build a library of local knowledge for Karnataka. 🌟",
    )
    logger.info("Local content submitted: id=%s type=%s phone=%s", entry.id, content_type, phone)
    await session_manager.set_state(phone, "MAIN")


# ---------------------------------------------------------------------------
# Photo received while in local content flow
# ---------------------------------------------------------------------------

async def handle_local_content_photo(
    phone: str,
    message_id: str,
    session: Session,
    db: AsyncSession,
) -> None:
    """Librarian sent a photo as their local content."""
    content_type = session.context.get("content_type", "other")
    label = session.context.get("label", "Content")

    entry = await _save_local_content(
        phone, session, content_type, db,
        photo_url=f"whatomate_media:{message_id}",
    )

    await whatomate.send_text(
        session.whatomate_contact_id,
        f"📸 Photo received! Your *{label}* has been saved.\n\n"
        "We will review it and share it with libraries across Karnataka. 🙏",
    )
    logger.info("Local content (photo) submitted: id=%s type=%s phone=%s", entry.id, content_type, phone)
    await session_manager.set_state(phone, "MAIN")


# ---------------------------------------------------------------------------
# Text received while in local content flow
# ---------------------------------------------------------------------------

async def handle_local_content_text(
    phone: str,
    text: str,
    session: Session,
    db: AsyncSession,
) -> None:
    """Librarian typed their content as text."""
    state = session.state
    cid = session.whatomate_contact_id

    if state == "FLOW_6_AWAITING_TYPE":
        # They typed instead of tapping — detect keywords
        content_type = _detect_content_type(text)
        label = content_type.capitalize()
        await session_manager.update_context(phone, {"content_type": content_type, "label": label})
        await session_manager.set_state(phone, "FLOW_6_AWAITING_CONTENT")
        await whatomate.send_text(
            cid,
            f"Got it — you would like to share a *{label}*.\n\n"
            "Please go ahead — type it, or send a voice note or photo.",
        )
        return

    if state == "FLOW_6_AWAITING_CONTENT":
        content_type = session.context.get("content_type", "other")
        label = session.context.get("label", "Content")

        entry = await _save_local_content(
            phone, session, content_type, db, description=text
        )

        await whatomate.send_text(
            cid,
            f"🙏 Thank you! Your *{label}* has been received:\n\n"
            f"\"{text[:200]}{'...' if len(text) > 200 else ''}\"\n\n"
            "We will review it and share it with libraries across Karnataka. 🌟",
        )
        logger.info("Local content (text) submitted: id=%s type=%s phone=%s", entry.id, content_type, phone)
        await session_manager.set_state(phone, "MAIN")
        return

    # Unexpected state
    await session_manager.set_state(phone, "MAIN")


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

async def _save_local_content(
    phone: str,
    session: Session,
    content_type: str,
    db: AsyncSession,
    description: str | None = None,
    voice_note_url: str | None = None,
    photo_url: str | None = None,
) -> LocalContent:
    lib_result = await db.execute(
        select(Librarian).where(Librarian.phone == phone)
    )
    librarian = lib_result.scalar_one_or_none()
    lib_id = librarian.id if librarian else _uuid.UUID(session.librarian_id)

    entry = LocalContent(
        librarian_id=lib_id,
        content_type=content_type,
        description=description,
        voice_note_url=voice_note_url,
        photo_url=photo_url,
        status="submitted",
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


def _detect_content_type(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ["story", "tale", "ಕಥೆ"]):
        return "story"
    if any(w in t for w in ["song", "sing", "ಹಾಡು"]):
        return "song"
    if any(w in t for w in ["game", "play", "ಆಟ"]):
        return "game"
    if any(w in t for w in ["craft", "make", "ಕರಕುಶಲ"]):
        return "craft"
    return "other"
