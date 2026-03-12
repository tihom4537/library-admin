"""
POST /arivu/webhook — Entry point for all inbound events from Whatomate.

Whatomate sends a POST here for every message.incoming event.
Payload shape (from Whatomate's webhook_dispatch.go):
{
    "event": "message.incoming",
    "timestamp": "2024-01-01T00:00:00Z",
    "data": {
        "message_id":       "uuid",
        "contact_id":       "uuid",          ← Whatomate's contact UUID
        "contact_phone":    "919876543210",
        "contact_name":     "Suma",
        "message_type":     "text|image|audio|nfm_reply|button_reply|...",
        "content":          "...",           ← for nfm_reply: JSON string of form data
        "whatsapp_account": "account-name",
        "direction":        "incoming"
    }
}

Routing logic:
  1. Verify HMAC signature from Whatomate
  2. Load session from Redis
  3. If no session / not onboarded → onboarding flow
  4. If in ONBOARDING state → handle onboarding response
  5. If message_type = image → photo documentation flow (Flow 2)
  6. If message_type = nfm_reply → process flow form submission
  7. If message_type = button_reply → handle button selection
  8. If message_type = audio → STT → classify intent → route
  9. If message_type = text → classify intent → route
"""
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.database import get_db
from app.flows.onboarding import (
    BTN_CONFIRM_NO,
    BTN_CONFIRM_YES,
    handle_onboarding_response,
    handle_unknown_phone,
    send_main_menu,
)
from app.flows.tech_support import (
    handle_tech_support_start,
    handle_tech_support_button,
    handle_tech_support_photo,
    handle_tech_support_text,
    ISSUE_TYPES as TECH_ISSUE_TYPES,
)
from app.flows.activity_ideas import (
    handle_activity_ideas_start,
    handle_activity_ideas_selection,
    handle_activity_ideas_button,
)
from app.flows.local_content import (
    handle_local_content_start,
    handle_local_content_button,
    handle_local_content_audio,
    handle_local_content_photo,
    handle_local_content_text,
    CONTENT_TYPE_LABELS,
)
from app.models.librarian import ConversationLog, Librarian
from app.sarvam import intent as intent_classifier
from app.session.manager import Session, session_manager
from app.whatomate.client import whatomate

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------

def _verify_signature(body: bytes, received_sig: str, secret: str) -> bool:
    """
    Verify Whatomate's HMAC-SHA256 signature.
    Header: X-Webhook-Signature: sha256=<hex>
    Returns True (pass) if secret is empty — skip verification in dev/test mode.
    """
    secret = secret.strip()
    if not secret:
        return True  # No secret configured: skip verification
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received_sig)


# ---------------------------------------------------------------------------
# Main webhook endpoint
# ---------------------------------------------------------------------------

@router.post("/arivu/webhook")
async def arivu_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.body()

    # Verify signature (skip if WHATOMATE_WEBHOOK_SECRET is empty in .env)
    sig = request.headers.get("X-Webhook-Signature", "")
    configured_secret = settings.whatomate_webhook_secret.strip()
    if configured_secret and not _verify_signature(body, sig, configured_secret):
        logger.warning("Webhook signature verification failed")
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event = payload.get("event", "")
    if event != "message.incoming":
        # We only process inbound messages; ignore message.sent etc.
        return {"status": "ignored"}

    data = payload.get("data", {})
    phone = data.get("contact_phone", "").strip()
    whatomate_contact_id = data.get("contact_id", "").strip()
    message_type = data.get("message_type", "text").strip()
    content = data.get("content", "").strip()
    message_id = data.get("message_id", "").strip()

    if not phone or not whatomate_contact_id:
        logger.error("Webhook missing phone or contact_id: %s", data)
        return {"status": "error", "detail": "missing required fields"}

    logger.info(
        "Incoming message: phone=%s type=%s content_len=%d",
        phone,
        message_type,
        len(content),
    )

    # Always return 200 to Whatomate — never let exceptions propagate.
    # A non-200 response causes Whatomate to retry the webhook repeatedly.
    try:
        await _dispatch(phone, whatomate_contact_id, message_type, content, message_id, db)
    except Exception as e:
        logger.error("Unhandled error in _dispatch (phone=%s): %s", phone, e, exc_info=True)

    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Dispatch logic
# ---------------------------------------------------------------------------

async def _dispatch(
    phone: str,
    whatomate_contact_id: str,
    message_type: str,
    content: str,
    message_id: str,
    db: AsyncSession,
) -> None:
    """Route the incoming message to the appropriate handler."""
    session = await session_manager.get(phone)

    # ── Step 1: Identify librarian ────────────────────────────────────────────
    if not session.librarian_id:
        # First time this phone has messaged, or session expired
        librarian = await _lookup_librarian(phone, db)
        if librarian is None:
            # Not in roster → onboarding will handle "not found" message
            await handle_unknown_phone(phone, whatomate_contact_id, db)
            return

        if librarian.status != "onboarded":
            await handle_unknown_phone(phone, whatomate_contact_id, db)
            return

        # Restore session for known onboarded librarian
        session = Session(
            librarian_id=str(librarian.id),
            whatomate_contact_id=whatomate_contact_id,
            state="MAIN",
        )
        await session_manager.save(phone, session)
        # Update whatomate_contact_id if missing
        if not librarian.whatomate_contact_id:
            librarian.whatomate_contact_id = whatomate_contact_id
            await db.commit()

    # Ensure whatomate_contact_id is always current
    if session.whatomate_contact_id != whatomate_contact_id:
        session.whatomate_contact_id = whatomate_contact_id
        await session_manager.save(phone, session)

    # Update last_active_at on every message
    await _touch_last_active(session.librarian_id, db)

    # ── Step 2: Route by state and message type ───────────────────────────────

    state = session.state

    # Onboarding confirmation (button_reply while in ONBOARDING state)
    if state == "ONBOARDING_AWAITING_CONFIRM" and message_type == "button_reply":
        button_id = _extract_button_id(content)
        await handle_onboarding_response(phone, button_id, session, db)
        return

    # WhatsApp Flow form submission (nfm_reply)
    if message_type == "nfm_reply":
        await _handle_flow_response(phone, content, session, db)
        return

    # ── Flow-specific state routing (before generic handlers) ─────────────────

    # Flow 3: Tech Support — mid-conversation states
    if state in ("FLOW_3_AWAITING_CATEGORY", "FLOW_3_AWAITING_FEEDBACK", "FLOW_3_AWAITING_PHOTO"):
        if message_type == "image":
            await handle_tech_support_photo(phone, message_id, session, db)
        elif message_type in ("button_reply", "interactive"):
            await handle_tech_support_button(phone, _extract_button_id(content), session, db)
        else:
            await handle_tech_support_text(phone, content, session, db)
        return

    # Flow 4: Activity Ideas — browsing state
    if state == "FLOW_4_BROWSING":
        if message_type in ("button_reply", "interactive"):
            button_id = _extract_button_id(content)
            if button_id in ("ideas_will_do", "ideas_see_more"):
                await handle_activity_ideas_button(phone, button_id, session, db)
            else:
                await handle_activity_ideas_selection(phone, button_id, session, db)
        else:
            await handle_activity_ideas_button(phone, "ideas_see_more", session, db)
        return

    # Flow 6: Local Content — mid-submission states
    if state in ("FLOW_6_AWAITING_TYPE", "FLOW_6_AWAITING_CONTENT"):
        if message_type == "image":
            await handle_local_content_photo(phone, message_id, session, db)
        elif message_type == "audio":
            await handle_local_content_audio(phone, message_id, session, db)
        elif message_type in ("button_reply", "interactive"):
            await handle_local_content_button(phone, _extract_button_id(content), session, db)
        else:
            await handle_local_content_text(phone, content, session, db)
        return

    # ── Generic handlers ──────────────────────────────────────────────────────

    # Photo received → trigger activity report flow (Flow 2)
    if message_type == "image":
        await _handle_photo(phone, message_id, session, db)
        return

    # Audio voice note → transcribe → classify
    if message_type == "audio":
        await _handle_audio(phone, message_id, session, db)
        return

    # Button reply (interactive button or list selection)
    if message_type in ("button_reply", "interactive"):
        button_id = _extract_button_id(content)
        await _handle_button(phone, button_id, session, db)
        return

    # Text message (the common path)
    if message_type == "text":
        await _handle_text(phone, content, session, db)
        return

    # Unknown message type — acknowledge gracefully
    await whatomate.send_text(
        session.whatomate_contact_id,
        "ಕ್ಷಮಿಸಿ, ಈ ರೀತಿಯ ಸಂದೇಶ ನನಗೆ ಅರ್ಥ ಆಗುವುದಿಲ್ಲ. "
        "ದಯಮಾಡಿ ಪಠ್ಯ ಅಥವಾ ಧ್ವನಿ ಸಂದೇಶ ಕಳುಹಿಸಿ.",
    )


# ---------------------------------------------------------------------------
# Message type handlers
# ---------------------------------------------------------------------------

async def _handle_text(phone: str, text: str, session: Session, db: AsyncSession) -> None:
    """Classify intent and route."""
    intent = await intent_classifier.classify_intent(text)
    logger.info("Intent: phone=%s intent=%s text=%r", phone, intent, text[:50])

    await _log_message(session.librarian_id, "incoming", "text", text, intent, db)
    await _route_by_intent(phone, intent, text, session, db)


async def _handle_audio(phone: str, message_id: str, session: Session, db: AsyncSession) -> None:
    """Download audio, transcribe with Sarvam STT, classify intent."""
    from app.sarvam import stt as stt_module

    try:
        audio_bytes = await whatomate.get_media(message_id)
        transcript = await stt_module.transcribe_audio(audio_bytes)
    except Exception as e:
        logger.error("Audio processing failed for %s: %s", phone, e)
        transcript = None

    if not transcript:
        await whatomate.send_text(
            session.whatomate_contact_id,
            "ಕ್ಷಮಿಸಿ, ನಿಮ್ಮ ಧ್ವನಿ ಸಂದೇಶ ಅರ್ಥ ಆಗಲಿಲ್ಲ. ದಯಮಾಡಿ ಪಠ್ಯದಲ್ಲಿ ಟೈಪ್ ಮಾಡಿ.",
        )
        return

    intent = await intent_classifier.classify_intent(transcript)
    await _log_message(session.librarian_id, "incoming", "audio", transcript, intent, db)
    await _route_by_intent(phone, intent, transcript, session, db)


async def _handle_photo(phone: str, message_id: str, session: Session, db: AsyncSession) -> None:
    """
    Photo received → store message_id → prompt them to open activity_report_flow.
    Phase 2: will trigger the actual WhatsApp Flow for report submission.
    """
    await session_manager.set_photo_pending(phone, message_id)

    # TODO (Phase 2): Send flow message using meta_client.send_flow_message(...)
    # For now send a text acknowledgment
    await whatomate.send_text(
        session.whatomate_contact_id,
        "📸 ಫೋಟೋ ಸ್ವೀಕರಿಸಲಾಯಿತು!\n\n"
        "ಚಟುವಟಿಕೆ ವಿವರ ತಿಳಿಸಿ (Phase 2 ರಲ್ಲಿ ಫಾರ್ಮ್ ತೆರೆಯುತ್ತದೆ).",
    )
    await _log_message(session.librarian_id, "incoming", "image", f"[photo:{message_id}]", None, db)


async def _handle_flow_response(
    phone: str,
    content: str,
    session: Session,
    db: AsyncSession,
) -> None:
    """
    Handle nfm_reply (WhatsApp Flow form submission).
    content = JSON string of form data (thanks to our Whatomate fix).
    """
    try:
        form_data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        logger.error("Failed to parse nfm_reply content for %s: %r", phone, content)
        return

    flow_token = form_data.get("flow_token") or session.context.get("flow_token")
    flow_meta = None
    if flow_token:
        flow_meta = await session_manager.resolve_flow_token(flow_token)
        await session_manager.delete_flow_token(flow_token)

    flow_type = (flow_meta or {}).get("flow_type") or session.context.get("flow_type", "unknown")
    logger.info("Flow response: phone=%s flow_type=%s data=%s", phone, flow_type, form_data)

    # Route by flow type
    if flow_type == "activity_report":
        await _process_activity_report(phone, form_data, session, db)
    elif flow_type == "activity_detail":
        await _process_activity_detail(phone, form_data, session, db)
    elif flow_type == "microlearning":
        await _process_microlearning_outcome(phone, form_data, session, db)
    else:
        logger.warning("Unknown flow type '%s' for %s", flow_type, phone)

    await _log_message(
        session.librarian_id, "incoming", "nfm_reply", content, None, db
    )


async def _handle_button(phone: str, button_id: str, session: Session, db: AsyncSession) -> None:
    """Handle button/list reply."""
    logger.info("Button reply: phone=%s button_id=%s state=%s", phone, button_id, session.state)

    if button_id in (BTN_CONFIRM_YES, BTN_CONFIRM_NO):
        await handle_onboarding_response(phone, button_id, session, db)
        return

    # Main menu numeric shortcuts
    menu_map = {
        "1": "check_activity",
        "2": "report_activity",
        "3": "tech_support",
        "4": "activity_ideas",
        "5": "learning",
        "6": "local_content",
    }
    if button_id in menu_map:
        await _route_by_intent(phone, menu_map[button_id], button_id, session, db)
        return

    # Generic: classify by button text as intent
    await _route_by_intent(phone, "unknown", button_id, session, db)


# ---------------------------------------------------------------------------
# Intent routing
# ---------------------------------------------------------------------------

async def _route_by_intent(
    phone: str,
    intent: str,
    text: str,
    session: Session,
    db: AsyncSession,
) -> None:
    """Route to the correct flow based on classified intent."""
    cid = session.whatomate_contact_id

    if intent == "greeting":
        from app.flows.onboarding import MAIN_MENU_TEXT
        await whatomate.send_text(cid, f"ನಮಸ್ಕಾರ! 🙏\n\n{MAIN_MENU_TEXT}")

    elif intent == "check_activity":
        # Phase 2: Flow 1 — check scheduled activities
        await whatomate.send_text(
            cid,
            "📅 ಚಟುವಟಿಕೆ ಮಾಹಿತಿ ಲೋಡ್ ಆಗುತ್ತಿದೆ... (Phase 2 ರಲ್ಲಿ ಸಂಪೂರ್ಣ ಜಾರಿಗೆ ಬರುತ್ತದೆ)",
        )

    elif intent == "report_activity":
        # Phase 2: Flow 2 — report activity
        await whatomate.send_text(
            cid,
            "📸 ಫೋಟೋ ಕಳುಹಿಸಿ ಅಥವಾ ಚಟುವಟಿಕೆ ವಿವರ ತಿಳಿಸಿ. (Phase 2 ರಲ್ಲಿ ಸಂಪೂರ್ಣ ಜಾರಿಗೆ ಬರುತ್ತದೆ)",
        )

    elif intent == "tech_support":
        await handle_tech_support_start(phone, session)

    elif intent == "activity_ideas":
        await handle_activity_ideas_start(phone, text, session, db)

    elif intent == "learning":
        # Phase 3: send microlearning_flow via Meta directly
        await whatomate.send_text(
            cid,
            "📖 Learning module — coming in Phase 3!\n\n"
            "Every Wednesday I will send you a new 3-minute learning module.",
        )

    elif intent == "local_content":
        await handle_local_content_start(phone, session)

    else:
        # Unknown intent — show main menu
        from app.flows.onboarding import MAIN_MENU_TEXT
        await whatomate.send_text(
            cid,
            f"ಕ್ಷಮಿಸಿ, ಅರ್ಥ ಆಗಲಿಲ್ಲ. 😊\n\n{MAIN_MENU_TEXT}",
        )


# ---------------------------------------------------------------------------
# Phase 2 flow response processors (stubs for now)
# ---------------------------------------------------------------------------

async def _process_activity_report(
    phone: str, form_data: dict, session: Session, db: AsyncSession
) -> None:
    """Save activity_report from flow submission. Full impl in Phase 2."""
    # TODO (Phase 2): Save ActivityReport to DB
    activity_id = form_data.get("activity_id", "?")
    children = form_data.get("children_count", "?")
    feedback = form_data.get("feedback", "?")

    await whatomate.send_text(
        session.whatomate_contact_id,
        f"✅ ದಾಖಲಾಯಿತು!\n\n"
        f"ಚಟುವಟಿಕೆ: {activity_id}\n"
        f"ಮಕ್ಕಳು: {children}\n"
        f"ಅನುಭವ: {feedback}\n\n"
        f"ಧನ್ಯವಾದ! 🙏",
    )
    await session_manager.set_state(phone, "MAIN")


async def _process_activity_detail(
    phone: str, form_data: dict, session: Session, db: AsyncSession
) -> None:
    """Handle activity_detail_flow response."""
    decision = form_data.get("decision", "")
    if decision == "will_do":
        await whatomate.send_text(
            session.whatomate_contact_id,
            "ಅದ್ಭುತ! ✅ ಚಟುವಟಿಕೆ ಮಾಡಿದ ನಂತರ ಫೋಟೋ ಕಳುಹಿಸಿ.",
        )
    else:
        # show_another — Phase 2: show another activity
        await whatomate.send_text(
            session.whatomate_contact_id,
            "ಸರಿ, ಇನ್ನೊಂದು ಚಟುವಟಿಕೆ ತೋರಿಸುತ್ತೇನೆ... (Phase 2 ರಲ್ಲಿ ಜಾರಿಗೆ ಬರುತ್ತದೆ)",
        )
    await session_manager.set_state(phone, "MAIN")


async def _process_microlearning_outcome(
    phone: str, form_data: dict, session: Session, db: AsyncSession
) -> None:
    """Handle microlearning_flow outcome response."""
    outcome = form_data.get("outcome", "")
    module_id = form_data.get("module_id", "")

    if outcome == "done":
        await whatomate.send_text(
            session.whatomate_contact_id,
            "ಶಾಭಾಸ್! 🎉 ಅಭ್ಯಾಸ ಮಾಡಿದ್ದಕ್ಕೆ ಧನ್ಯವಾದ!",
        )
        # TODO (Phase 3): Mark LibrarianLearningProgress.practice_completed = True
    else:
        # problem — route to tech support
        await whatomate.send_text(
            session.whatomate_contact_id,
            "ತೊಂದರೆ ಆಯಿತು ಎಂದು ತಿಳಿಸಿ — ಸಮಸ್ಯೆ ಏನು?",
        )
    await session_manager.set_state(phone, "MAIN")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_button_id(content: str) -> str:
    """Extract button ID from content. Content may be a JSON string or raw ID."""
    if not content:
        return ""
    try:
        data = json.loads(content)
        return data.get("id") or data.get("button_id") or content
    except (json.JSONDecodeError, TypeError):
        return content


async def _lookup_librarian(phone: str, db: AsyncSession) -> Librarian | None:
    result = await db.execute(select(Librarian).where(Librarian.phone == phone))
    return result.scalar_one_or_none()


async def _touch_last_active(librarian_id: str, db: AsyncSession) -> None:
    import uuid as _uuid
    result = await db.execute(
        select(Librarian).where(Librarian.id == _uuid.UUID(librarian_id))
    )
    lib = result.scalar_one_or_none()
    if lib:
        lib.last_active_at = datetime.now(timezone.utc)
        await db.commit()


async def _log_message(
    librarian_id: str,
    direction: str,
    message_type: str,
    content: str,
    intent: str | None,
    db: AsyncSession,
) -> None:
    import uuid as _uuid
    try:
        log = ConversationLog(
            librarian_id=_uuid.UUID(librarian_id),
            direction=direction,
            message_type=message_type,
            content=content[:4000] if content else None,
            intent_classified=intent,
        )
        db.add(log)
        await db.commit()
    except Exception as e:
        logger.error("Failed to log message: %s", e)
