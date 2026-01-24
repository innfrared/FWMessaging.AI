from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.domain.entities.message import Message


class WebhookEventDTO(BaseModel):
    object: str | None = None
    entry: list[dict[str, Any]] = Field(default_factory=list)

    def extract_messages(self) -> list[Message]:
        messages: list[Message] = []
        for entry in self.entry or []:
            for msg in entry.get("messaging", []) or []:
                message = msg.get("message") or {}
                text = message.get("text")
                mid = message.get("mid")
                sender = (msg.get("sender") or {}).get("id")
                recipient = (msg.get("recipient") or {}).get("id")
                timestamp = msg.get("timestamp")

                if not (mid and sender and text and timestamp):
                    continue

                thread_id = str(sender)
                messages.append(
                    Message(
                        id=str(mid),
                        thread_id=thread_id,
                        sender_id=str(sender),
                        text=str(text),
                        timestamp=int(timestamp),
                        platform="instagram",
                    )
                )

                if recipient:
                    _ = str(recipient)

        return messages
