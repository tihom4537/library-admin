"""
Meta WhatsApp Cloud API client.
Used specifically for sending WhatsApp Flow messages, because Whatomate's REST API
does not expose flow message sending via its HTTP interface.

All other messages (text, interactive, templates) go through Whatomate's API.

Docs: https://developers.facebook.com/docs/whatsapp/flows/guides/sendingaflow
"""
import logging
import uuid

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

META_API_BASE = "https://graph.facebook.com"


class MetaClient:
    def __init__(self):
        self.phone_number_id = settings.meta_phone_number_id
        self.access_token = settings.meta_access_token
        self.api_version = settings.meta_api_version
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def _messages_url(self) -> str:
        return f"{META_API_BASE}/{self.api_version}/{self.phone_number_id}/messages"

    async def send_flow_message(
        self,
        to_phone: str,
        flow_id: str,
        flow_cta: str,
        body_text: str,
        first_screen: str,
        screen_data: dict | None = None,
        header_text: str | None = None,
        flow_token: str | None = None,
    ) -> dict:
        """
        Send a WhatsApp Flow message to a phone number.

        Args:
            to_phone:     Recipient phone number (e.g. "919876543210")
            flow_id:      Meta Flow ID (obtained after publishing flow)
            flow_cta:     Button text on the flow CTA (max 20 chars, e.g. "ತೆರೆಯಿರಿ")
            body_text:    Body text shown above the CTA button
            first_screen: Name of the first screen in the flow (e.g. "ACTIVITY_REPORT")
            screen_data:  Data to pass to the first screen (fills ${data.xxx} variables)
            header_text:  Optional header text
            flow_token:   Unique token to correlate this send with the response.
                         Auto-generated if not provided.

        Returns:
            Meta API response JSON
        """
        token = flow_token or str(uuid.uuid4())

        action_payload: dict = {
            "screen": first_screen,
        }
        if screen_data:
            action_payload["data"] = screen_data

        interactive: dict = {
            "type": "flow",
            "body": {"text": body_text},
            "footer": {"text": ""},
            "action": {
                "name": "flow",
                "parameters": {
                    "flow_message_version": "3",
                    "flow_token": token,
                    "flow_id": flow_id,
                    "flow_cta": flow_cta,
                    "flow_action": "navigate",
                    "flow_action_payload": action_payload,
                },
            },
        }

        if header_text:
            interactive["header"] = {"type": "text", "text": header_text}

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": "interactive",
            "interactive": interactive,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(self._messages_url(), json=payload, headers=self.headers)
                resp.raise_for_status()
                result = resp.json()
                logger.info("Flow message sent to %s (token=%s)", to_phone, token)
                return {"token": token, "meta_response": result}
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Meta API error sending flow: %s → %s",
                    e.request.url,
                    e.response.text,
                )
                raise

    async def send_template_message(
        self,
        to_phone: str,
        template_name: str,
        language_code: str = "kn",
        components: list[dict] | None = None,
    ) -> dict:
        """
        Send a pre-approved template message directly via Meta API.
        Prefer using Whatomate's /api/messages/template for tracked sends.
        This method is a fallback or for scheduler jobs.
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                "components": components or [],
            },
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(self._messages_url(), json=payload, headers=self.headers)
            resp.raise_for_status()
            return resp.json()


# Singleton instance
meta_client = MetaClient()
