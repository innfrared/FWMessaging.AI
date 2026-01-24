from abc import ABC, abstractmethod

from app.domain.entities.response_template import ResponseTemplate


class KnowledgeBasePort(ABC):
    @abstractmethod
    def get_template(self, intent: str, service: str | None, language: str) -> ResponseTemplate | None:
        raise NotImplementedError

    @abstractmethod
    def resolve_service_from_text(self, text: str) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def get_service_display_name(self, service: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def is_ambiguous_category_question(self, text: str) -> str | None:
        """
        Detect ambiguous category questions that need clarification.
        Returns the category name if ambiguous, None otherwise.
        """
        raise NotImplementedError

    @abstractmethod
    def get_service_facts(self, service: str, language: str) -> str | None:
        """
        Get service facts (e.g., session guidance) for a given service.
        Returns the fact text in the specified language, or None if not available.
        """
        raise NotImplementedError

    @abstractmethod
    def get_canonical_service_message(self, service_key: str, language: str) -> list[str] | None:
        """
        Get canonical service message lines for a service registry key.
        Returns list of message lines, or None if not available.
        """
        raise NotImplementedError

    @abstractmethod
    def resolve_service_to_registry_key(self, text: str) -> str | None:
        """
        Resolve user text to a service registry key using registry aliases.
        Returns registry key (e.g., "laser_hair_removal_full_body") or None.
        """
        raise NotImplementedError
