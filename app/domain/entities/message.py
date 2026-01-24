from dataclasses import dataclass


@dataclass(frozen=True)
class Message:
    id: str
    thread_id: str
    sender_id: str
    text: str
    timestamp: int
    platform: str
