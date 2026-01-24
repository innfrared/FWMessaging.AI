from __future__ import annotations

import logging

from app.application.ports.message_platform import MessagePlatformPort
from app.core.config import settings


class SendReplyUseCase:
    def __init__(self, platform: MessagePlatformPort) -> None:
        self._platform = platform
        self._logger = logging.getLogger(__name__)

    def execute(self, recipient_id: str, text: str) -> bool:
        """Send a reply. Returns True if actually sent, False if skipped."""
        if not settings.AUTO_REPLY_ENABLED:
            self._logger.info("WOULD_SEND_REPLY", extra={"thread_id": recipient_id, "text": text})
            self._logger.info("AUTO_REPLY_ENABLED=false -> skipping send")
            return False
        self._platform.send_text(recipient_id=recipient_id, text=text)
        return True
