from __future__ import annotations

import logging

from app.application.ports.message_platform import MessagePlatformPort


class MockInstagramPlatform(MessagePlatformPort):
    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    def send_text(self, recipient_id: str, text: str) -> None:
        self._logger.info(
            "Mock send to Instagram", extra={"recipient_id": recipient_id, "text": text}
        )
