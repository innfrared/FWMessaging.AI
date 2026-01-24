from __future__ import annotations

import logging

from app.application.ports.knowledge_base import KnowledgeBasePort
from app.application.use_cases.reply_composer import ReplyComposer
from app.domain.entities.reply import Reply


class GenerateReplyUseCase:
    def __init__(self, kb: KnowledgeBasePort) -> None:
        self._kb = kb
        self._logger = logging.getLogger(__name__)
        self._composer = ReplyComposer(kb=kb)

    def execute(
        self,
        intent: str,
        service: str | None,
        language: str,
        greeting_applicable: bool,
        yesno_answer: str | None,
        include_location: bool,
        booking_only_cta: bool,
        explicit_price_intent: bool = False,
        include_equipment: bool = False,
        include_session_facts: bool = False,
        user_message_text: str | None = None,
        booking_result: "BookingResult | None" = None,
    ) -> Reply:
        from app.application.use_cases.booking import BookingResult

        composed = self._composer.compose(
            intent=intent,
            resolved_service=service,
            language=language,
            greeting_applicable=greeting_applicable,
            yesno_answer=yesno_answer,
            include_location=include_location,
            booking_only_cta=booking_only_cta,
            explicit_price_intent=explicit_price_intent,
            include_equipment=include_equipment,
            include_session_facts=include_session_facts,
            user_message_text=user_message_text,
            booking_result=booking_result,
        )
        if composed.error:
            self._logger.error(
                "Reply validation failed",
                extra={"reason": composed.error, "intent": intent, "service": service, "language": language},
            )
            return Reply(text="", should_handoff=True, handoff_reason=composed.error, meta={})

        return Reply(text=composed.text, should_handoff=False, handoff_reason="", meta={})
