"""
Redis-backed session state manager.

Redis key: arivu:session:{phone} → JSON blob
TTL: 30 minutes (reset on each interaction)

Session schema:
{
    "librarian_id": "uuid-string",
    "whatomate_contact_id": "uuid-string",
    "state": "IDLE|ONBOARDING|MAIN|FLOW_1|FLOW_2|...",
    "context": {}   // arbitrary dict for current flow context
}

States:
  IDLE        → no active conversation, awaiting first message
  ONBOARDING  → in the middle of onboarding verification
  MAIN        → onboarded, at main menu, routing by intent
  FLOW_1      → check_activity: viewing activity list
  FLOW_2      → report_activity: processing photo + form
  FLOW_3      → tech_support: waiting for follow-up
  FLOW_4      → activity_ideas: browsing suggestions
  FLOW_5      → micro_learning: in learning flow
  FLOW_6      → local_content: submitting local story/craft
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

SESSION_TTL_SECONDS = 30 * 60  # 30 minutes
SESSION_KEY_PREFIX = "arivu:session:"
FLOW_TOKEN_PREFIX = "arivu:flow_token:"
PHOTO_PENDING_PREFIX = "arivu:photo_pending:"


@dataclass
class Session:
    librarian_id: str = ""
    whatomate_contact_id: str = ""
    state: str = "IDLE"
    context: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "librarian_id": self.librarian_id,
            "whatomate_contact_id": self.whatomate_contact_id,
            "state": self.state,
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        return cls(
            librarian_id=data.get("librarian_id", ""),
            whatomate_contact_id=data.get("whatomate_contact_id", ""),
            state=data.get("state", "IDLE"),
            context=data.get("context", {}),
        )


class SessionManager:
    def __init__(self):
        self._redis: aioredis.Redis | None = None

    async def connect(self):
        self._redis = await aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        logger.info("Session manager connected to Redis")

    async def disconnect(self):
        if self._redis:
            await self._redis.aclose()

    def _key(self, phone: str) -> str:
        return f"{SESSION_KEY_PREFIX}{phone}"

    def _flow_token_key(self, token: str) -> str:
        return f"{FLOW_TOKEN_PREFIX}{token}"

    def _photo_pending_key(self, phone: str) -> str:
        return f"{PHOTO_PENDING_PREFIX}{phone}"

    async def get(self, phone: str) -> Session:
        """Load session from Redis; return empty IDLE session if not found."""
        raw = await self._redis.get(self._key(phone))
        if not raw:
            return Session()
        return Session.from_dict(json.loads(raw))

    async def save(self, phone: str, session: Session) -> None:
        """Persist session to Redis with 30-min TTL."""
        await self._redis.setex(
            self._key(phone),
            SESSION_TTL_SECONDS,
            json.dumps(session.to_dict()),
        )

    async def clear(self, phone: str) -> None:
        """Delete session (reset to IDLE)."""
        await self._redis.delete(self._key(phone))

    async def set_state(self, phone: str, state: str, context: dict | None = None) -> Session:
        """Update just the state and optionally the context, preserving other fields."""
        session = await self.get(phone)
        session.state = state
        if context is not None:
            session.context = context
        await self.save(phone, session)
        return session

    async def update_context(self, phone: str, updates: dict) -> Session:
        """Merge updates into the session context dict."""
        session = await self.get(phone)
        session.context.update(updates)
        await self.save(phone, session)
        return session

    # -------------------------------------------------------------------------
    # Flow token registry
    # Used to correlate flow sends with their responses.
    # When we send a flow message we store:
    #   flow_token → {flow_type, phone, context_data}
    # When nfm_reply comes in, we look up the token to know which flow to process.
    # -------------------------------------------------------------------------

    async def register_flow_token(
        self,
        token: str,
        flow_type: str,
        phone: str,
        context: dict | None = None,
    ) -> None:
        """Store flow token mapping for 24 hours (user has 24h to submit the form)."""
        data = {
            "flow_type": flow_type,
            "phone": phone,
            "context": context or {},
        }
        await self._redis.setex(
            self._flow_token_key(token),
            24 * 60 * 60,
            json.dumps(data),
        )

    async def resolve_flow_token(self, token: str) -> dict | None:
        """Look up flow token; returns None if expired or unknown."""
        raw = await self._redis.get(self._flow_token_key(token))
        if not raw:
            return None
        return json.loads(raw)

    async def delete_flow_token(self, token: str) -> None:
        await self._redis.delete(self._flow_token_key(token))

    # -------------------------------------------------------------------------
    # Photo pending registry
    # When a librarian sends a photo, we store it temporarily awaiting
    # their form submission (activity_report_flow).
    # -------------------------------------------------------------------------

    async def set_photo_pending(self, phone: str, message_id: str) -> None:
        """Store the Whatomate message_id of the pending photo for 60 minutes."""
        await self._redis.setex(
            self._photo_pending_key(phone),
            60 * 60,
            message_id,
        )

    async def get_photo_pending(self, phone: str) -> str | None:
        """Return the pending photo message_id, or None."""
        return await self._redis.get(self._photo_pending_key(phone))

    async def clear_photo_pending(self, phone: str) -> None:
        await self._redis.delete(self._photo_pending_key(phone))


# Singleton — connected during app startup
session_manager = SessionManager()
