from abc import ABC, abstractmethod


class MessagePlatformPort(ABC):
    @abstractmethod
    def send_text(self, recipient_id: str, text: str) -> None:
        raise NotImplementedError
