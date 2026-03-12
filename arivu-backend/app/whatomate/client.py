"""
Whatomate REST API client.
Used to send outgoing messages back to librarians via Whatomate's bridge.

All message types except WhatsApp Flows go through this client.
Flows are sent directly via Meta's Cloud API (see app/meta/client.py).

Auth: X-API-Key header
Base URL: WHATOMATE_BASE_URL (default: http://localhost:8080)
"""
import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class WhatomateClient:
    def __init__(self):
        self.base_url = settings.whatomate_base_url.rstrip("/")
        self.headers = {
            "X-API-Key": settings.whatomate_api_key,
            "Content-Type": "application/json",
        }

    async def send_text(self, contact_id: str, text: str) -> dict:
        """Send a plain text message to a contact."""
        payload = {
            "type": "text",
            "content": {"body": text},
        }
        return await self._post(f"/api/contacts/{contact_id}/messages", payload)

    async def send_buttons(
        self,
        contact_id: str,
        body_text: str,
        buttons: list[dict],  # [{"id": "opt1", "title": "Option 1"}, ...]
    ) -> dict:
        """Send an interactive button message (max 3 buttons)."""
        payload = {
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": body_text,
                "buttons": buttons,
            },
        }
        return await self._post(f"/api/contacts/{contact_id}/messages", payload)

    async def send_list(
        self,
        contact_id: str,
        body_text: str,
        rows: list[dict],  # [{"id": "item1", "title": "Item 1"}, ...]
    ) -> dict:
        """Send an interactive list message (for showing activity options etc.)."""
        payload = {
            "type": "interactive",
            "interactive": {
                "type": "list",
                "body": body_text,
                "buttons": rows,
            },
        }
        return await self._post(f"/api/contacts/{contact_id}/messages", payload)

    async def send_cta_url(
        self,
        contact_id: str,
        body_text: str,
        button_text: str,
        url: str,
    ) -> dict:
        """Send a CTA URL button message."""
        payload = {
            "type": "interactive",
            "interactive": {
                "type": "cta_url",
                "body": body_text,
                "button_text": button_text,
                "url": url,
            },
        }
        return await self._post(f"/api/contacts/{contact_id}/messages", payload)

    async def send_template(
        self,
        phone_number: str,
        template_name: str,
        params: dict[str, str] | None = None,
    ) -> dict:
        """
        Send a pre-approved WhatsApp message template.
        Used for proactive outbound messages (nudges, reminders).
        """
        payload = {
            "phone_number": phone_number,
            "template_name": template_name,
            "template_params": params or {},
        }
        return await self._post("/api/messages/template", payload)

    async def create_contact(self, phone_number: str, name: str | None = None) -> dict:
        """
        Ensure a contact exists in Whatomate for this phone number.
        Returns the contact record (id is the contact_id for sending messages).
        """
        payload = {"phone_number": phone_number}
        if name:
            payload["name"] = name
        return await self._post("/api/contacts", payload)

    async def get_contact_by_id(self, contact_id: str) -> dict:
        """Get a contact record by Whatomate contact UUID."""
        return await self._get(f"/api/contacts/{contact_id}")

    async def get_media(self, message_id: str) -> bytes:
        """
        Download media from a Whatomate message (image, audio, document).
        Returns raw bytes of the media file.
        """
        url = f"{self.base_url}/api/media/{message_id}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(url, headers=self.headers)
            resp.raise_for_status()
            return resp.content

    async def _get(self, path: str) -> dict:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=self.headers)
            resp.raise_for_status()
            return resp.json()

    async def _post(self, path: str, payload: dict) -> dict:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(url, json=payload, headers=self.headers)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Whatomate API error: %s %s → %s",
                    e.request.method,
                    e.request.url,
                    e.response.text,
                )
                raise


# Singleton instance
whatomate = WhatomateClient()
