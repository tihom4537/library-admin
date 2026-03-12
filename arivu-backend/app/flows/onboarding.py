"""
Flow 0: Librarian Onboarding

Triggered when an unknown phone number messages the bot.

States used: ONBOARDING_AWAITING_CONFIRM

Flow:
1. Phone not in librarian table → check if phone matches pending roster
2. If match found → "ನಮಸ್ಕಾರ! ನೀವು [Name], [Library], [District]? (✅ ಹೌದು / ❌ ಅಲ್ಲ)"
3. If confirmed → mark onboarded_at, set state=MAIN, send welcome + main menu
4. If denied or not found → "ಮೊದಲು ಇಲಾಖೆಯಲ್ಲಿ ನೋಂದಣಿ ಮಾಡಿ"
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.librarian import Librarian
from app.session.manager import Session, session_manager
from app.whatomate.client import whatomate

logger = logging.getLogger(__name__)

# Confirmation button IDs
BTN_CONFIRM_YES = "onboard_yes"
BTN_CONFIRM_NO = "onboard_no"

MAIN_MENU_TEXT = (
    "ಮುಖ್ಯ ಮೆನು:\n\n"
    "1️⃣  ಈ ವಾರ ಏನು ಮಾಡಬೇಕು?\n"
    "2️⃣  ಚಟುವಟಿಕೆ ದಾಖಲಿಸಿ\n"
    "3️⃣  ತಾಂತ್ರಿಕ ಸಹಾಯ\n"
    "4️⃣  ಚಟುವಟಿಕೆ ಆಯ್ಡಿಯಾ\n\n"
    "ಅಥವಾ ನೇರವಾಗಿ ಹೇಳಿ — ನಾನು ಅರ್ಥ ಮಾಡಿಕೊಳ್ಳುತ್ತೇನೆ! 😊"
)


async def handle_unknown_phone(
    phone: str,
    whatomate_contact_id: str,
    db: AsyncSession,
) -> None:
    """
    Entry point for a phone number we've never seen before.
    Tries to match to the librarian roster; starts onboarding if found.
    """
    result = await db.execute(select(Librarian).where(Librarian.phone == phone))
    librarian = result.scalar_one_or_none()

    if librarian is None:
        # Phone not in roster at all
        await whatomate.send_text(
            whatomate_contact_id,
            "ಕ್ಷಮಿಸಿ, ನಿಮ್ಮ ಫೋನ್ ನಂಬರ್ ನಮ್ಮ ಗ್ರಂಥಾಲಯ ಪಟ್ಟಿಯಲ್ಲಿ ಇಲ್ಲ. "
            "ಮೊದಲು ಇಲಾಖೆಯಲ್ಲಿ ನೋಂದಣಿ ಮಾಡಿ ಅಥವಾ ಮೇಲ್ವಿಚಾರಕರನ್ನು ಸಂಪರ್ಕಿಸಿ.",
        )
        return

    if librarian.status == "onboarded":
        # Already onboarded — maybe they cleared their chat; restore session
        await _restore_session(phone, librarian, whatomate_contact_id)
        return

    # Found in roster but not yet onboarded — start verification
    await _start_verification(phone, librarian, whatomate_contact_id, db)


async def _start_verification(
    phone: str,
    librarian: Librarian,
    whatomate_contact_id: str,
    db: AsyncSession,
) -> None:
    """Send confirmation prompt and store pending state."""
    # Save whatomate_contact_id on librarian record
    librarian.whatomate_contact_id = whatomate_contact_id
    await db.commit()

    session = await session_manager.get(phone)
    session.librarian_id = str(librarian.id)
    session.whatomate_contact_id = whatomate_contact_id
    session.state = "ONBOARDING_AWAITING_CONFIRM"
    await session_manager.save(phone, session)

    await whatomate.send_buttons(
        whatomate_contact_id,
        f"ನಮಸ್ಕಾರ! 🙏\n\n"
        f"ನೀವು *{librarian.name}*,\n"
        f"*{librarian.library_name}*,\n"
        f"*{librarian.district or ''}* ಅಲ್ಲವೇ?",
        buttons=[
            {"id": BTN_CONFIRM_YES, "title": "✅ ಹೌದು"},
            {"id": BTN_CONFIRM_NO, "title": "❌ ಅಲ್ಲ"},
        ],
    )


async def handle_onboarding_response(
    phone: str,
    button_id: str,
    session: Session,
    db: AsyncSession,
) -> None:
    """
    Handle the librarian's Yes/No response to the identity confirmation.
    """
    if button_id == BTN_CONFIRM_YES:
        await _complete_onboarding(phone, session, db)
    else:
        # They said "No" — maybe wrong number or wrong entry
        await session_manager.clear(phone)
        await whatomate.send_text(
            session.whatomate_contact_id,
            "ಕ್ಷಮಿಸಿ! ದಯಮಾಡಿ ನಿಮ್ಮ ಮೇಲ್ವಿಚಾರಕರನ್ನು ಸಂಪರ್ಕಿಸಿ ಮತ್ತು "
            "ನಿಮ್ಮ ಮೊಬೈಲ್ ನಂಬರ್ ಅನ್ನು ಪಟ್ಟಿಯಲ್ಲಿ ಸೇರಿಸಲು ಹೇಳಿ.",
        )


async def _complete_onboarding(
    phone: str,
    session: Session,
    db: AsyncSession,
) -> None:
    """Mark librarian as onboarded and send welcome message."""
    import uuid as _uuid
    librarian_id = _uuid.UUID(session.librarian_id)
    result = await db.execute(select(Librarian).where(Librarian.id == librarian_id))
    librarian = result.scalar_one_or_none()

    if librarian:
        librarian.status = "onboarded"
        librarian.onboarded_at = datetime.now(timezone.utc)
        librarian.last_active_at = datetime.now(timezone.utc)
        await db.commit()

    session.state = "MAIN"
    await session_manager.save(phone, session)

    name = librarian.name if librarian else "ಗ್ರಂಥಾಲಯಾಧ್ಯಕ್ಷರೇ"

    await whatomate.send_text(
        session.whatomate_contact_id,
        f"ಸ್ವಾಗತ, *{name}*! 🎉\n\n"
        f"ಅರಿವು ಕೇಂದ್ರ ಬೋಟ್‌ಗೆ ಸುಸ್ವಾಗತ.\n\n"
        f"{MAIN_MENU_TEXT}",
    )


async def _restore_session(
    phone: str,
    librarian: Librarian,
    whatomate_contact_id: str,
) -> None:
    """Librarian is already onboarded but has no active Redis session."""
    session = Session(
        librarian_id=str(librarian.id),
        whatomate_contact_id=whatomate_contact_id,
        state="MAIN",
    )
    await session_manager.save(phone, session)

    await whatomate.send_text(
        whatomate_contact_id,
        f"ಮತ್ತೊಮ್ಮೆ ಸ್ವಾಗತ, *{librarian.name}*! 🙏\n\n{MAIN_MENU_TEXT}",
    )


async def send_main_menu(whatomate_contact_id: str) -> None:
    """Send the main menu to an already-onboarded librarian."""
    await whatomate.send_text(whatomate_contact_id, MAIN_MENU_TEXT)
