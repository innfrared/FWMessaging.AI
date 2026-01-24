from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from app.application.ports.calendar import CalendarPort
from app.application.ports.conversation_store import ConversationStorePort
from app.application.ports.knowledge_base import KnowledgeBasePort
from app.application.ports.service_catalog import ServiceCatalogPort
from app.application.use_cases.booking import BookingResult, BookingUseCase
from app.application.use_cases.selection import SelectionResult, SelectionUseCase
from app.application.utils.context_resolver import resolve_context
from app.application.utils.state_helpers import reset_all_transient, reset_booking_state
from app.domain.entities.booking_state import BookingState
from app.domain.entities.selection_state import SelectionState
from app.application.use_cases.classify_intent import ClassifyIntentUseCase
from app.application.use_cases.detect_outside_business import evaluate_outside_business
from app.application.use_cases.generate_reply import GenerateReplyUseCase
from app.application.use_cases.send_reply import SendReplyUseCase
from app.application.utils.duration_answer import build_duration_response
from app.application.utils.greeting import is_follow_up
from app.application.utils.message_rules import (
    asks_about_duration,
    asks_about_results,
    asks_about_sessions,
    contains_date_or_time,
    contains_location_request,
    extract_service_query,
    has_equipment_intent,
    has_explicit_price_intent,
    is_brazilian_query,
    is_booking_request,
    is_informational_question,
    is_service_existence_question,
    is_yes_no_question,
)
from app.core.config import settings
from app.domain.entities.conversation_state import ConversationState
from app.domain.entities.message import Message


class HandleIncomingMessageUseCase:
    def __init__(
        self,
        store: ConversationStorePort,
        kb: KnowledgeBasePort,
        classify_intent: ClassifyIntentUseCase,
        generate_reply: GenerateReplyUseCase,
        send_reply: SendReplyUseCase,
        booking_use_case: BookingUseCase | None,
        service_catalog: ServiceCatalogPort | None,
        business_name: str,
        business_tone: str,
        auto_reply_enabled: bool,
    ) -> None:
        self._store = store
        self._kb = kb
        self._classify_intent = classify_intent
        self._generate_reply = generate_reply
        self._send_reply = send_reply
        self._booking_use_case = booking_use_case
        self._service_catalog = service_catalog
        self._business_name = business_name
        self._business_tone = business_tone
        self._auto_reply_enabled = auto_reply_enabled
        self._selection_use_case = SelectionUseCase(kb)
        self._logger = logging.getLogger(__name__)

    def handle(self, message: Message) -> None:
        try:
            if self._store.has_processed(message.id):
                self._logger.info("Duplicate message ignored", extra={"message_id": message.id})
                return

            now_ts = _now_ts(settings.BUSINESS_TIMEZONE)
            should_process, previous_message_id = self._store.should_process_message(
                message.thread_id, message.id, cooldown_seconds=3.0, now_ts=now_ts
            )
            if not should_process:
                self._logger.info(
                    "Message coalesced",
                    extra={
                        "event": "message_coalesced",
                        "thread_id": message.thread_id,
                        "previous_message_id": previous_message_id,
                        "current_message_id": message.id,
                    },
                )
                return

            self._store.mark_message_received(message.thread_id, message.id, now_ts)
            self._store.mark_processed(message.id)

            self._store.append_message(
                message.thread_id,
                role="user",
                text=message.text,
                meta={"message_id": message.id, "sender_id": message.sender_id, "platform": message.platform},
            )

            state = self._store.get_state(message.thread_id)
            
            # Update last_seen_at
            state = ConversationState(
                last_intent=state.last_intent,
                awaiting_booking=state.awaiting_booking,
                last_service=state.last_service,
                booking_state=state.booking_state,
                language=state.language,
                last_seen_at=now_ts,
                last_outbound_at=state.last_outbound_at,
                greeted_at=state.greeted_at,
                selection_state=state.selection_state,
            )
            self._store.set_state(message.thread_id, state)

            # Get recent messages for context
            recent_messages = self._store.get_recent_messages(message.thread_id, limit=10)
            
            # Resolve context using ContextResolver
            context = resolve_context(
                thread_id=message.thread_id,
                user_text=message.text,
                recent_messages=recent_messages,
                state=state,
                kb=self._kb,
            )
            
            # Update state with resolved language
            if context.resolved_language != state.language:
                state = ConversationState(
                    last_intent=state.last_intent,
                    awaiting_booking=state.awaiting_booking,
                    last_service=state.last_service,
                    booking_state=state.booking_state,
                    language=context.resolved_language,
                    last_seen_at=state.last_seen_at,
                    last_outbound_at=state.last_outbound_at,
                    greeted_at=state.greeted_at,
                    selection_state=state.selection_state,
                )
                self._store.set_state(message.thread_id, state)

            # Context routing: Check booking state first
            booking_result: BookingResult | None = None
            selection_result: SelectionResult | None = None
            in_booking_flow = False
            in_selection_flow = False
            
            if state.booking_state.status != "none":
                # In booking flow - route ONLY through BookingUseCase
                in_booking_flow = True
                # Check for explicit cancellation
                normalized = message.text.lower().strip()
                cancel_keywords = ("cancel", "stop", "never mind", "no thanks", "cancelar", "no gracias")
                if any(keyword in normalized for keyword in cancel_keywords):
                    state = reset_booking_state(state)
                    self._store.set_state(message.thread_id, state)
                    # After cancellation, fall through to normal flow to generate a reply
                    in_booking_flow = False
                elif self._booking_use_case:
                    # Continue booking flow
                    booking_result = self._booking_use_case.process_booking_intent(
                        message_text=message.text,
                        current_state=state.booking_state,
                        service=context.resolved_service_key,
                        language=context.resolved_language,
                        conversation_state=state,
                    )
                    new_booking_state = booking_result.updated_state
                    state = ConversationState(
                        last_intent=state.last_intent,
                        awaiting_booking=state.awaiting_booking,
                        last_service=state.last_service or context.resolved_service_key,
                        booking_state=new_booking_state,
                        language=state.language,
                        last_seen_at=state.last_seen_at,
                        last_outbound_at=state.last_outbound_at,
                        greeted_at=state.greeted_at,
                        selection_state=state.selection_state,
                    )
                    self._store.set_state(message.thread_id, state)
            elif state.selection_state.status == "awaiting_service_choice":
                # In selection flow - route through SelectionUseCase
                in_selection_flow = True
                selection_result = self._selection_use_case.process_selection_intent(
                    message_text=message.text,
                    current_state=state.selection_state,
                    language=context.resolved_language,
                )
                new_selection_state = selection_result.updated_state
                state = ConversationState(
                    last_intent=state.last_intent,
                    awaiting_booking=state.awaiting_booking,
                    last_service=state.last_service or selection_result.service_key,
                    booking_state=state.booking_state,
                    language=state.language,
                    last_seen_at=state.last_seen_at,
                    last_outbound_at=state.last_outbound_at,
                    greeted_at=state.greeted_at,
                    selection_state=new_selection_state,
                )
                self._store.set_state(message.thread_id, state)
            
            # Generate reply based on flow
            self._logger.info(
                "Flow routing decision",
                extra={
                    "message_id": message.id,
                    "thread_id": message.thread_id,
                    "in_booking_flow": in_booking_flow,
                    "booking_result_exists": booking_result is not None,
                    "in_selection_flow": in_selection_flow,
                    "booking_state_status": state.booking_state.status,
                    "selection_state_status": state.selection_state.status,
                },
            )
            
            if in_booking_flow and booking_result:
                # Generate reply for booking flow
                greeting_applicable = False
                if context.resolved_language in {"en", "es"} and not context.is_follow_up:
                    if self._store.should_greet_today(message.thread_id, settings.BUSINESS_TIMEZONE, now_ts):
                        greeting_applicable = True
                        self._store.mark_greeted(message.thread_id, now_ts)
                
                reply = self._generate_reply.execute(
                    intent="booking",
                    service=context.resolved_service_key or state.last_service,
                    language=context.resolved_language,
                    greeting_applicable=greeting_applicable,
                    yesno_answer=None,
                    include_location=False,
                    booking_only_cta=True,
                    explicit_price_intent=context.is_price_question,
                    include_equipment=False,
                    include_session_facts=False,
                    user_message_text=message.text,
                    booking_result=booking_result,
                )
                
                if reply.text.strip() and self._auto_reply_enabled:
                    did_send = self._send_reply.execute(recipient_id=message.sender_id, text=reply.text)
                    if did_send:
                        self._store.append_message(
                            message.thread_id,
                            role="assistant",
                            text=reply.text,
                            meta=reply.meta or {},
                        )
                        self._store.mark_outbound(message.thread_id, now_ts)
                        self._logger.info("Reply sent", extra={"event": "reply_sent", "message_id": message.id, "thread_id": message.thread_id})
                
                # Update state with last_intent
                state = ConversationState(
                    last_intent="booking",
                    awaiting_booking=state.awaiting_booking,
                    last_service=state.last_service,
                    booking_state=state.booking_state,
                    language=state.language,
                    last_seen_at=state.last_seen_at,
                    last_outbound_at=state.last_outbound_at,
                    greeted_at=state.greeted_at,
                    selection_state=state.selection_state,
                )
                self._store.set_state(message.thread_id, state)
                return
            
            # Normal flow (including selection flow) - classify intent but override with service registry
            self._logger.info(
                "Entering normal flow",
                extra={
                    "message_id": message.id,
                    "thread_id": message.thread_id,
                    "message_text": message.text[:100],
                },
            )
            classification = self._classify_intent.execute(message.text, None)
            self._logger.info(
                "Intent classified",
                extra={
                    "message_id": message.id,
                    "thread_id": message.thread_id,
                    "intent": classification.intent,
                    "service": classification.service,
                    "language": classification.language,
                },
            )
            
            # Service registry match beats LLM intent
            resolved_service = context.resolved_service_key or self._kb.resolve_service_to_registry_key(message.text)
            booking_request = context.is_booking_request
            
            self._logger.info(
                "Service resolution",
                extra={
                    "message_id": message.id,
                    "thread_id": message.thread_id,
                    "resolved_service": resolved_service,
                    "booking_request": booking_request,
                },
            )
            
            if resolved_service:
                classification = classification.__class__(
                    intent=classification.intent,
                    language=context.resolved_language,
                    normalized_text=classification.normalized_text,
                    service=resolved_service,
                )
                if classification.intent == "services_list":
                    classification = classification.__class__(
                        intent="service_details",
                        language=context.resolved_language,
                        normalized_text=classification.normalized_text,
                        service=resolved_service,
                    )
                    self._logger.info(
                        "Intent changed to service_details",
                        extra={
                            "message_id": message.id,
                            "thread_id": message.thread_id,
                            "service": resolved_service,
                        },
                    )
            elif classification.intent in {"pricing", "availability", "booking"} and state.last_service and not booking_request:
                classification = classification.__class__(
                    intent=classification.intent,
                    language=context.resolved_language,
                    normalized_text=classification.normalized_text,
                    service=state.last_service,
                )
            elif classification.intent == "pricing":
                classification = classification.__class__(
                    intent="services_list",
                    language=context.resolved_language,
                    normalized_text=classification.normalized_text,
                    service=None,
                )
            
            # Check if should enter booking flow
            explicit_booking_request = context.is_booking_request
            has_date_or_time_info = contains_date_or_time(message.text)
            is_informational = is_informational_question(message.text)
            is_results_question = asks_about_results(message.text)
            
            booking_state_active = state.booking_state.status in {"collecting_date", "collecting_time", "confirming"}
            is_booking_reply = booking_state_active and has_date_or_time_info
            
            booking_signal = explicit_booking_request or (classification.intent in {"booking", "availability"} and not is_informational and not is_results_question)
            should_enter_booking_flow = booking_signal or is_booking_reply
            
            self._logger.info(
                "Booking flow check",
                extra={
                    "message_id": message.id,
                    "thread_id": message.thread_id,
                    "explicit_booking_request": explicit_booking_request,
                    "has_date_or_time_info": has_date_or_time_info,
                    "is_informational": is_informational,
                    "is_results_question": is_results_question,
                    "booking_state_active": booking_state_active,
                    "is_booking_reply": is_booking_reply,
                    "booking_signal": booking_signal,
                    "should_enter_booking_flow": should_enter_booking_flow,
                    "has_booking_use_case": self._booking_use_case is not None,
                },
            )
            
            if should_enter_booking_flow and self._booking_use_case:
                self._logger.info(
                    "Entering booking flow processing",
                    extra={
                        "message_id": message.id,
                        "thread_id": message.thread_id,
                    },
                )
                try:
                    booking_result = self._booking_use_case.process_booking_intent(
                        message_text=message.text,
                        current_state=state.booking_state,
                        service=resolved_service,
                        language=context.resolved_language,
                        conversation_state=state,
                    )
                    new_booking_state = booking_result.updated_state
                    state = ConversationState(
                        last_intent=state.last_intent,
                        awaiting_booking=state.awaiting_booking,
                        last_service=state.last_service or resolved_service,
                        booking_state=new_booking_state,
                        language=state.language,
                        last_seen_at=state.last_seen_at,
                        last_outbound_at=state.last_outbound_at,
                        greeted_at=state.greeted_at,
                        selection_state=state.selection_state,
                    )
                    self._store.set_state(message.thread_id, state)
                    self._logger.info(
                        "Booking flow processing completed",
                        extra={
                            "message_id": message.id,
                            "thread_id": message.thread_id,
                            "booking_state_status": new_booking_state.status,
                        },
                    )
                except Exception as e:
                    self._logger.exception(
                        "Error in booking flow processing",
                        extra={
                            "message_id": message.id,
                            "thread_id": message.thread_id,
                            "error": str(e),
                        },
                    )
                    booking_result = None
            
            # Use context flags for reply generation
            explicit_price_intent = context.is_price_question
            equipment_intent = context.is_equipment_question
            session_intent = context.is_sessions_question
            duration_intent = context.is_duration_question
            
            self._logger.info(
                "Context flags set",
                extra={
                    "message_id": message.id,
                    "thread_id": message.thread_id,
                    "explicit_price_intent": explicit_price_intent,
                    "equipment_intent": equipment_intent,
                    "session_intent": session_intent,
                    "duration_intent": duration_intent,
                },
            )
            
            # Check greeting
            greeting_applicable = False
            try:
                if context.resolved_language in {"en", "es"} and not context.is_follow_up:
                    self._logger.info(
                        "Checking if should greet",
                        extra={
                            "message_id": message.id,
                            "thread_id": message.thread_id,
                            "language": context.resolved_language,
                            "is_follow_up": context.is_follow_up,
                        },
                    )
                    should_greet = self._store.should_greet_today(message.thread_id, settings.BUSINESS_TIMEZONE, now_ts)
                    self._logger.info(
                        "should_greet_today returned",
                        extra={
                            "message_id": message.id,
                            "thread_id": message.thread_id,
                            "should_greet": should_greet,
                        },
                    )
                    if should_greet:
                        greeting_applicable = True
                        self._store.mark_greeted(message.thread_id, now_ts)
                        self._logger.info(
                            "Greeting marked",
                            extra={
                                "message_id": message.id,
                                "thread_id": message.thread_id,
                            },
                        )
            except Exception as e:
                import traceback
                error_str = f"Error in greeting check: {type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
                self._logger.error(error_str, exc_info=True, extra={
                    "message_id": message.id,
                    "thread_id": message.thread_id,
                })
                print(f"ERROR: {error_str}")  # Fallback print
            
            self._logger.info(
                "Greeting check done",
                extra={
                    "message_id": message.id,
                    "thread_id": message.thread_id,
                    "greeting_applicable": greeting_applicable,
                },
            )
            
            # Generate reply for normal flow
            self._logger.info(
                "Checking duration intent path",
                extra={
                    "message_id": message.id,
                    "thread_id": message.thread_id,
                    "duration_intent": duration_intent,
                    "resolved_service": resolved_service,
                    "has_service_catalog": self._service_catalog is not None,
                },
            )
            if duration_intent and resolved_service and self._service_catalog:
                duration_response = build_duration_response(
                    service_key=resolved_service,
                    catalog=self._service_catalog,
                    language=classification.language,
                    include_price=explicit_price_intent,
                )
                reply = self._generate_reply.execute(
                    intent="service_details",
                    service=resolved_service,
                    language=classification.language,
                    greeting_applicable=greeting_applicable,
                    yesno_answer=duration_response,
                    include_location=False,
                    booking_only_cta=False,
                    explicit_price_intent=explicit_price_intent,
                    include_equipment=False,
                    include_session_facts=False,
                    user_message_text=message.text,
                    booking_result=None,
                )
                if self._auto_reply_enabled and reply.text:
                    did_send = self._send_reply.execute(
                        recipient_id=message.sender_id,
                        text=reply.text,
                    )
                    if did_send:
                        self._logger.info(
                            "Reply sent",
                            extra={
                                "event": "reply_sent",
                                "message_id": message.id,
                                "thread_id": message.thread_id,
                                "platform": message.platform,
                            },
                        )
                    else:
                        self._logger.info(
                            "Reply skipped",
                            extra={
                                "event": "reply_skipped",
                                "message_id": message.id,
                                "thread_id": message.thread_id,
                                "reason": "AUTO_REPLY_ENABLED=false",
                            },
                        )
                # Update state with last_intent and last_service
                state = ConversationState(
                    last_intent=classification.intent,
                    awaiting_booking=state.awaiting_booking,
                    last_service=state.last_service or classification.service or context.resolved_service_key,
                    booking_state=state.booking_state,
                    language=state.language,
                    last_seen_at=state.last_seen_at,
                    last_outbound_at=state.last_outbound_at,
                    greeted_at=state.greeted_at,
                    selection_state=state.selection_state,
                )
                self._store.set_state(message.thread_id, state)
                return

            self._logger.info(
                "Checking intent modification",
                extra={
                    "message_id": message.id,
                    "thread_id": message.thread_id,
                    "intent": classification.intent,
                    "explicit_price_intent": explicit_price_intent,
                },
            )
            if classification.intent in {"pricing", "service_details"}:
                if not explicit_price_intent:
                    if classification.intent == "pricing":
                        if "availability" in message.text.lower() or "spots" in message.text.lower() or "available" in message.text.lower():
                            classification = classification.__class__(
                                intent="availability",
                                language=classification.language,
                                normalized_text=classification.normalized_text,
                                service=classification.service,
                            )
                        else:
                            classification = classification.__class__(
                                intent="services_list",
                                language=classification.language,
                                normalized_text=classification.normalized_text,
                                service=None,
                            )
                    elif classification.intent == "service_details":
                        if "availability" in message.text.lower() or "spots" in message.text.lower() or "available" in message.text.lower():
                            classification = classification.__class__(
                                intent="availability",
                                language=classification.language,
                                normalized_text=classification.normalized_text,
                                service=classification.service,
                            )
                        else:
                            classification = classification.__class__(
                                intent="services_list",
                                language=classification.language,
                                normalized_text=classification.normalized_text,
                                service=None,
                            )

            if equipment_intent and classification.intent == "availability":
                pass

            self._logger.info(
                "Intent classified",
                extra={
                    "message_id": message.id,
                    "intent": classification.intent,
                    "language": classification.language,
                    "service": classification.service,
                    "explicit_price_intent": explicit_price_intent,
                    "equipment_intent": equipment_intent,
                    "session_intent": session_intent,
                },
            )

            self._logger.info(
                "Getting template",
                extra={
                    "message_id": message.id,
                    "thread_id": message.thread_id,
                    "intent": classification.intent,
                    "service": classification.service,
                    "language": classification.language,
                },
            )
            try:
                template = self._kb.get_template(
                    classification.intent,
                    classification.service,
                    classification.language,
                )
                self._logger.info(
                    "Template retrieved",
                    extra={
                        "message_id": message.id,
                        "thread_id": message.thread_id,
                        "template_exists": template is not None,
                    },
                )
                decision = evaluate_outside_business(classification.intent, template)
                self._logger.info(
                    "Business hours check",
                    extra={
                        "message_id": message.id,
                        "thread_id": message.thread_id,
                        "should_handoff": decision.should_handoff,
                        "reason": decision.reason,
                    },
                )
            except Exception as e:
                self._logger.exception(
                    "Error getting template or checking business hours",
                    extra={
                        "message_id": message.id,
                        "thread_id": message.thread_id,
                        "error": str(e),
                    },
                )
                # Continue with None template - let the flow continue
                template = None
                decision = type('Decision', (), {'should_handoff': False, 'reason': ''})()
            if decision.should_handoff:
                self._store.append_message(
                    message.thread_id,
                    role="system",
                    text=f"HANDOFF: {decision.reason}",
                    meta={
                        "message_id": message.id,
                        "intent": classification.intent,
                        "language": classification.language,
                        "decision": decision.reason,
                    },
                )
                self._logger.info(
                    "Handoff decided pre-reply",
                    extra={"event": "reply_suppressed", "message_id": message.id, "reason": decision.reason, "intent": classification.intent},
                )
                return

            yes_no = is_yes_no_question(message.text)
            brazilian_query = is_brazilian_query(message.text)
            include_location = contains_location_request(message.text) and classification.intent != "location"

            greeting_applicable = False
            if classification.language in {"en", "es"} and not is_follow_up(message.text):
                now_ts = _now_ts(settings.BUSINESS_TIMEZONE)
                if self._store.should_greet_today(message.thread_id, settings.BUSINESS_TIMEZONE, now_ts):
                    greeting_applicable = True
                    self._store.mark_greeted(message.thread_id, now_ts)
            yesno_answer = self._build_yesno_answer(
                intent=classification.intent,
                service=classification.service,
                language=classification.language,
                yes_no_question=yes_no,
                brazilian_query=brazilian_query,
                message_text=message.text,
            )

            reply = self._generate_reply.execute(
                intent=classification.intent,
                service=classification.service,
                language=classification.language,
                greeting_applicable=greeting_applicable,
                yesno_answer=yesno_answer,
                include_location=include_location,
                booking_only_cta=should_enter_booking_flow and (explicit_booking_request or is_booking_reply),
                explicit_price_intent=explicit_price_intent,
                include_equipment=equipment_intent,
                include_session_facts=session_intent,
                user_message_text=message.text,
                booking_result=booking_result,
            )

            self._logger.info(
                "Reply generated",
                extra={
                    "message_id": message.id,
                    "thread_id": message.thread_id,
                    "intent": classification.intent,
                    "reply_length": len(reply.text) if reply.text else 0,
                    "should_handoff": reply.should_handoff,
                    "handoff_reason": reply.handoff_reason,
                    "auto_reply_enabled": self._auto_reply_enabled,
                },
            )

            reply_sent = False

            if reply.should_handoff:
                self._store.append_message(
                    message.thread_id,
                    role="system",
                    text=f"HANDOFF: {reply.handoff_reason}",
                    meta={"message_id": message.id, **(reply.meta or {})},
                )
                self._logger.info(
                    "Handoff decided by validation",
                    extra={"event": "reply_suppressed", "message_id": message.id, "thread_id": message.thread_id, "reason": reply.handoff_reason},
                )
                return

            if reply.text.strip():
                if greeting_applicable:
                    self._logger.info(
                        "Greeting applied",
                        extra={
                            "event": "greeting_applied",
                            "message_id": message.id,
                            "thread_id": message.thread_id,
                            "language": classification.language,
                        },
                    )

                if self._auto_reply_enabled:
                    did_send = self._send_reply.execute(recipient_id=message.sender_id, text=reply.text)
                    if did_send:
                        self._store.append_message(
                            message.thread_id,
                            role="assistant",
                            text=reply.text,
                            meta=reply.meta or {},
                        )
                        self._store.mark_outbound(message.thread_id, _now_ts(settings.BUSINESS_TIMEZONE))
                        reply_sent = True
                        self._logger.info(
                            "Reply sent",
                            extra={"event": "reply_sent", "message_id": message.id, "thread_id": message.thread_id},
                        )
                    else:
                        self._logger.info(
                            "Reply skipped",
                            extra={"event": "reply_suppressed", "message_id": message.id, "thread_id": message.thread_id, "reason": "AUTO_REPLY_ENABLED=false"},
                        )
                else:
                    self._logger.info(
                        "Reply would be sent but AUTO_REPLY_ENABLED=false",
                        extra={
                            "event": "reply_suppressed",
                            "message_id": message.id,
                            "thread_id": message.thread_id,
                            "reply_text": reply.text[:100],
                            "reason": "AUTO_REPLY_ENABLED=false",
                        },
                    )

                if booking_request and classification.intent == "booking":
                    self._store.append_message(
                        message.thread_id,
                        role="system",
                        text="HANDOFF: booking_request",
                        meta={"message_id": message.id},
                    )
                    return
            else:
                self._logger.warning(
                    "Empty reply text; skipping send",
                    extra={"event": "reply_suppressed", "message_id": message.id, "thread_id": message.thread_id, "reason": "empty_reply_text"},
                )

            # Update state with last_intent and last_service
            updated_state = ConversationState(
                last_intent=classification.intent,
                awaiting_booking=state.awaiting_booking,
                last_service=state.last_service or classification.service or context.resolved_service_key,
                booking_state=state.booking_state,
                language=state.language,
                last_seen_at=state.last_seen_at,
                last_outbound_at=state.last_outbound_at,
                greeted_at=state.greeted_at,
                selection_state=state.selection_state,
            )
            self._store.set_state(message.thread_id, updated_state)
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code if e.response else None
            is_403 = status_code == 403

            error_details = {}
            if e.response:
                try:
                    error_json = e.response.json()
                    error_info = error_json.get("error", {})
                    error_details = {
                        "error_code": error_info.get("code"),
                        "error_message": error_info.get("message"),
                        "error_subcode": error_info.get("error_subcode"),
                        "error_type": error_info.get("type"),
                    }
                except Exception:
                    error_details = {"error_body": e.response.text[:200]}

            self._logger.error(
                "Instagram API error",
                extra={
                    "message_id": message.id,
                    "thread_id": message.thread_id,
                    "status_code": status_code,
                    "is_403_forbidden": is_403,
                    **error_details,
                },
            )

            if is_403:
                self._logger.warning(
                    "Instagram 403 Forbidden - possible causes: rate limiting, expired token, insufficient permissions, or 24h messaging window expired. "
                    "Check: 1) Token validity, 2) Page permissions, 3) 24h messaging window, 4) Rate limits",
                    extra={"message_id": message.id, "thread_id": message.thread_id},
                )
                reply_text = None
                try:
                    if 'reply' in locals() and hasattr(reply, 'text'):
                        reply_text = reply.text
                except Exception:
                    pass

                self._store.append_message(
                    message.thread_id,
                    role="system",
                    text="FAILED_SEND: Instagram 403 Forbidden",
                    meta={
                        "message_id": message.id,
                        "error_type": "instagram_403",
                        "original_reply": reply_text,
                    },
                )
        except Exception as e:
            error_type = type(e).__name__
            error_message = str(e)

            self._logger.exception(
                "Failed to handle incoming message",
                extra={
                    "message_id": message.id,
                    "thread_id": message.thread_id,
                    "error_type": error_type,
                    "error_message": error_message,
                },
            )


    def _build_yesno_answer(
        self,
        intent: str,
        service: str | None,
        language: str,
        yes_no_question: bool,
        brazilian_query: bool,
        message_text: str,
    ) -> str | None:
        if not yes_no_question:
            return None

        resolved_service = self._kb.resolve_service_from_text(message_text)
        if resolved_service:
            service_display = self._kb.get_service_display_name(resolved_service)
            if language == "es":
                return f"Si, ofrecemos {service_display}."
            return f"Yes, we offer {service_display}."

        service_display = self._kb.get_service_display_name(service) if service else None

        if intent in {"availability", "booking", "pricing"} and service_display:
            if brazilian_query:
                if language == "es":
                    return "Si, ofrecemos Brazilian. Por favor confirma si es Brazilian solamente o full body."
                return "Yes, we offer Brazilian. Please confirm if Brazilian only or full body."
            if language == "es":
                return f"Si, tenemos disponibilidad para {service_display}."
            return f"Yes, we have availability for {service_display}."

        if intent in {"availability", "booking"} and not service_display:
            if language == "es":
                return "Si."
            return "Yes."

        if intent == "location":
            if language == "es":
                return "Si, estamos en Burbank."
            return "Yes, we are in Burbank."

        if intent == "hours":
            if language == "es":
                return "Si, estamos abiertos de lunes a domingo 10:00 AM a 7:00 PM."
            return "Yes, we are open Monday to Sunday 10:00 AM to 7:00 PM."

        return None

    def _build_unsupported_service_response(self, message: Message, language: str, missing_service: str) -> str | None:
        return None


def _update_state(state: ConversationState, intent: str, service: str | None) -> ConversationState:
    awaiting_booking = state.awaiting_booking
    if intent in {"booking", "availability"}:
        awaiting_booking = True
    elif intent == "closing":
        awaiting_booking = False

    return ConversationState(
        last_intent=intent,
        awaiting_booking=awaiting_booking,
        last_service=service or state.last_service,
    )


def _now_ts(timezone: str) -> float:
    tz = _safe_timezone(timezone)
    return datetime.now(tz).timestamp()


def _safe_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("UTC")


def _unsupported_service_line(language: str, missing_service: str) -> str | None:
    return None
