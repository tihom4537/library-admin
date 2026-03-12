"""
Flow 3: Tech Support

Conversation states:
  MAIN → (tech_support intent) → show issue type buttons
  FLOW_3_AWAITING_CATEGORY → librarian picks issue type
  FLOW_3_AWAITING_FEEDBACK → showed steps, waiting "Did it help?"
  FLOW_3_AWAITING_PHOTO → escalation path, waiting for photo

Button IDs:
  tech_power | tech_internet | tech_keyboard | tech_shiksha | tech_other
  tech_yes_resolved | tech_no_broken
  tech_escalate_yes | tech_escalate_no
"""
import logging
import uuid as _uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.librarian import Librarian
from app.models.support import TechSupportTicket
from app.session.manager import Session, session_manager
from app.whatomate.client import whatomate

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Issue type definitions (button_id → display label + troubleshooting steps)
# ---------------------------------------------------------------------------

ISSUE_TYPES = {
    "tech_power": {
        "label": "💻 Computer not turning on",
        "steps": (
            "Try these steps:\n\n"
            "1️⃣ Check that the power cable is plugged in tightly at the back of the computer.\n"
            "2️⃣ Check that the power strip / switchboard is switched ON.\n"
            "3️⃣ Press and hold the power button for 5 seconds, then release.\n"
            "4️⃣ Wait 30 seconds and try the power button once more.\n\n"
            "Did this help?"
        ),
    },
    "tech_internet": {
        "label": "🌐 Internet not working",
        "steps": (
            "Try these steps:\n\n"
            "1️⃣ Check the Wi-Fi or LAN cable is connected to the computer.\n"
            "2️⃣ Restart the router — switch it OFF, wait 30 seconds, switch ON.\n"
            "3️⃣ On the computer, open a browser and try opening google.com.\n"
            "4️⃣ If it still doesn't work, check if other devices (phone) have internet.\n\n"
            "Did this help?"
        ),
    },
    "tech_keyboard": {
        "label": "⌨️ Keyboard / mouse not working",
        "steps": (
            "Try these steps:\n\n"
            "1️⃣ Unplug the keyboard/mouse USB cable and plug it back in.\n"
            "2️⃣ Try a different USB port on the computer.\n"
            "3️⃣ Restart the computer.\n"
            "4️⃣ Check if the keyboard or mouse has an ON/OFF switch (some wireless ones do).\n\n"
            "Did this help?"
        ),
    },
    "tech_shiksha": {
        "label": "📚 Shikshanapedia not opening",
        "steps": (
            "Try these steps:\n\n"
            "1️⃣ Double-click the Shikshanapedia icon on the desktop (wait 10-15 seconds).\n"
            "2️⃣ If the screen is blank, check that the internet is working.\n"
            "3️⃣ Try opening it in a different browser (Chrome or Edge).\n"
            "4️⃣ Close all open windows and restart Shikshanapedia.\n\n"
            "Did this help?"
        ),
    },
    "tech_other": {
        "label": "🔧 Other issue",
        "steps": (
            "Please describe your issue in detail — type or send a voice note.\n\n"
            "I will try to help or forward it to the support team."
        ),
    },
}

FEEDBACK_BUTTONS = [
    {"type": "reply", "reply": {"id": "tech_yes_resolved", "title": "✅ Yes, it worked!"}},
    {"type": "reply", "reply": {"id": "tech_no_broken", "title": "❌ No, still broken"}},
]

ESCALATE_BUTTONS = [
    {"type": "reply", "reply": {"id": "tech_escalate_yes", "title": "📸 Send photo"}},
    {"type": "reply", "reply": {"id": "tech_escalate_no", "title": "Skip for now"}},
]


# ---------------------------------------------------------------------------
# Entry point — called when intent = tech_support
# ---------------------------------------------------------------------------

async def handle_tech_support_start(phone: str, session: Session) -> None:
    """Show issue category buttons."""
    await session_manager.set_state(phone, "FLOW_3_AWAITING_CATEGORY")
    await whatomate.send_buttons(
        session.whatomate_contact_id,
        body=(
            "What is the issue?\n\n"
            "Select the type of problem and I will walk you through the fix."
        ),
        buttons=[
            {"type": "reply", "reply": {"id": k, "title": v["label"][:20]}}
            for k, v in list(ISSUE_TYPES.items())[:3]  # WhatsApp allows max 3 buttons per message
        ],
    )
    # Send second set of options as a follow-up
    await whatomate.send_buttons(
        session.whatomate_contact_id,
        body="More options:",
        buttons=[
            {"type": "reply", "reply": {"id": "tech_keyboard", "title": "⌨️ Keyboard/mouse"}},
            {"type": "reply", "reply": {"id": "tech_other", "title": "🔧 Other issue"}},
        ],
    )


# ---------------------------------------------------------------------------
# Button handler — routes within tech support flow
# ---------------------------------------------------------------------------

async def handle_tech_support_button(
    phone: str,
    button_id: str,
    session: Session,
    db: AsyncSession,
) -> None:
    """Handle all button replies within the tech support flow."""
    state = session.state
    cid = session.whatomate_contact_id

    # ── User selected an issue category ──────────────────────────────────────
    if button_id in ISSUE_TYPES and state == "FLOW_3_AWAITING_CATEGORY":
        issue = ISSUE_TYPES[button_id]
        ticket = await _create_ticket(phone, button_id, session, db)

        await session_manager.update_context(phone, {
            "issue_type": button_id,
            "ticket_id": str(ticket.id),
        })
        await session_manager.set_state(phone, "FLOW_3_AWAITING_FEEDBACK")

        if button_id == "tech_other":
            # Free-form — just ask them to describe
            await whatomate.send_text(cid, issue["steps"])
        else:
            await whatomate.send_buttons(cid, body=issue["steps"], buttons=FEEDBACK_BUTTONS)
        return

    # ── "Yes it worked" ───────────────────────────────────────────────────────
    if button_id == "tech_yes_resolved":
        ticket_id = session.context.get("ticket_id")
        if ticket_id:
            await _update_ticket_status(ticket_id, "resolved", db)
        await whatomate.send_text(
            cid,
            "Great! Glad it's working now. 😊\n\n"
            "Feel free to message me any time you need help.",
        )
        await session_manager.set_state(phone, "MAIN")
        return

    # ── "No, still broken" ────────────────────────────────────────────────────
    if button_id == "tech_no_broken":
        await session_manager.set_state(phone, "FLOW_3_AWAITING_PHOTO")
        await whatomate.send_buttons(
            cid,
            body=(
                "No worries — let me escalate this to the support team.\n\n"
                "Can you send a photo of the problem? They will call you back."
            ),
            buttons=ESCALATE_BUTTONS,
        )
        return

    # ── Escalation: librarian will send photo ─────────────────────────────────
    if button_id == "tech_escalate_yes":
        await whatomate.send_text(
            cid,
            "Please send the photo now — I will attach it to your support ticket.",
        )
        # State stays FLOW_3_AWAITING_PHOTO so _handle_photo can pick it up
        return

    # ── Escalation: skip photo ────────────────────────────────────────────────
    if button_id == "tech_escalate_no":
        ticket_id = session.context.get("ticket_id")
        if ticket_id:
            await _update_ticket_status(ticket_id, "escalated", db)
        await whatomate.send_text(
            cid,
            "Understood. Your issue has been logged.\n\n"
            "The support team will follow up with you soon.",
        )
        await session_manager.set_state(phone, "MAIN")
        return


# ---------------------------------------------------------------------------
# Photo received while in tech support escalation
# ---------------------------------------------------------------------------

async def handle_tech_support_photo(
    phone: str,
    message_id: str,
    session: Session,
    db: AsyncSession,
) -> None:
    """Librarian sent an escalation photo."""
    ticket_id = session.context.get("ticket_id")
    if ticket_id:
        await _update_ticket_status(ticket_id, "escalated", db, photo_message_id=message_id)

    await whatomate.send_text(
        session.whatomate_contact_id,
        "📸 Photo received and added to your ticket.\n\n"
        "The support team will review and call you back. Thank you for your patience! 🙏",
    )
    await session_manager.set_state(phone, "MAIN")


# ---------------------------------------------------------------------------
# Free-text while in tech support (FLOW_3_AWAITING_FEEDBACK)
# ---------------------------------------------------------------------------

async def handle_tech_support_text(
    phone: str,
    text: str,
    session: Session,
    db: AsyncSession,
) -> None:
    """User typed a description instead of tapping a button."""
    state = session.state
    cid = session.whatomate_contact_id

    if state == "FLOW_3_AWAITING_CATEGORY":
        # They typed the issue description — treat as "other"
        ticket = await _create_ticket(phone, "tech_other", session, db)
        await session_manager.update_context(phone, {"ticket_id": str(ticket.id), "issue_type": "tech_other"})
        await session_manager.set_state(phone, "FLOW_3_AWAITING_FEEDBACK")
        await whatomate.send_buttons(
            cid,
            body=(
                f"I have noted your issue: \"{text[:100]}\"\n\n"
                "I will forward this to the support team. Do you want to send a photo of the problem?"
            ),
            buttons=ESCALATE_BUTTONS,
        )
    elif state == "FLOW_3_AWAITING_FEEDBACK":
        await whatomate.send_buttons(
            cid,
            body="Did the steps help resolve the problem?",
            buttons=FEEDBACK_BUTTONS,
        )
    else:
        await whatomate.send_text(
            cid,
            "Your message is noted. Type 'help' any time to start a new support request.",
        )
        await session_manager.set_state(phone, "MAIN")


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

async def _create_ticket(
    phone: str, issue_type: str, session: Session, db: AsyncSession
) -> TechSupportTicket:
    lib_result = await db.execute(
        select(Librarian).where(Librarian.phone == phone)
    )
    librarian = lib_result.scalar_one_or_none()
    if not librarian:
        # Fallback: use session librarian_id
        lib_id = _uuid.UUID(session.librarian_id)
    else:
        lib_id = librarian.id

    followup_due = datetime.now(timezone.utc) + timedelta(hours=4)
    ticket = TechSupportTicket(
        librarian_id=lib_id,
        issue_type=issue_type,
        issue_description=ISSUE_TYPES.get(issue_type, {}).get("label", issue_type),
        status="open",
        followup_due_at=followup_due,
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)
    logger.info("Created tech support ticket %s for %s issue=%s", ticket.id, phone, issue_type)
    return ticket


async def _update_ticket_status(
    ticket_id: str,
    status: str,
    db: AsyncSession,
    photo_message_id: str | None = None,
) -> None:
    result = await db.execute(
        select(TechSupportTicket).where(TechSupportTicket.id == _uuid.UUID(ticket_id))
    )
    ticket = result.scalar_one_or_none()
    if ticket:
        ticket.status = status
        if status == "resolved":
            ticket.resolved_at = datetime.now(timezone.utc)
        if photo_message_id:
            ticket.photo_url = f"whatomate_media:{photo_message_id}"
        await db.commit()
