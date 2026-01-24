from __future__ import annotations

from app.application.ports.message_platform import MessagePlatformPort
from app.infrastructure.instagram.instagram_client import InstagramClient


class InstagramPlatform(MessagePlatformPort):
    def __init__(self, client: InstagramClient) -> None:
        self._client = client

    def send_text(self, recipient_id: str, text: str) -> None:
        self._client.send_text(recipient_id=recipient_id, text=text)
