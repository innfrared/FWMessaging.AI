from functools import lru_cache
import logging
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.infrastructure.llm.mock_llm import MockLLM
from app.infrastructure.llm.openai_llm import OpenAILLM
from app.infrastructure.store.json_store import JsonConversationStore
from app.infrastructure.store.memory_store import MemoryConversationStore
from app.application.use_cases.generate_reply import GenerateReplyUseCase
from app.application.use_cases.send_reply import SendReplyUseCase
from app.application.use_cases.handle_incoming_message import HandleIncomingMessageUseCase
from app.application.use_cases.classify_intent import ClassifyIntentUseCase
from app.application.use_cases.booking import BookingUseCase
from app.infrastructure.knowledge.structured_kb import build_kb
from app.infrastructure.knowledge.service_catalog_store import ServiceCatalogStore
from app.infrastructure.calendar.cal_com_client import CalComCalendar
from app.infrastructure.calendar.mock_calendar import MockCalendar
from app.infrastructure.instagram.instagram_client import InstagramClient
from app.infrastructure.instagram.instagram_platform import InstagramPlatform
from app.infrastructure.instagram.mock_platform import MockInstagramPlatform
from app.application.ports.calendar import CalendarPort
from app.application.ports.service_catalog import ServiceCatalogPort


_conversation_store: MemoryConversationStore | JsonConversationStore | None = None


@lru_cache
def get_llm():
    if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.strip():
        return OpenAILLM()
    return MockLLM()


def get_conversation_store() -> MemoryConversationStore | JsonConversationStore:
    global _conversation_store
    if _conversation_store is None:
        if settings.ENV.lower() in {"dev", "local"}:
            _conversation_store = JsonConversationStore()
        else:
            _conversation_store = MemoryConversationStore()
    return _conversation_store


def get_knowledge_base():
    return build_kb()


def get_service_catalog() -> ServiceCatalogPort:
    return ServiceCatalogStore()


def get_calendar() -> CalendarPort:
    if not settings.CAL_COM_API_KEY or settings.ENV.lower() in {"dev", "local"}:
        return MockCalendar()
    return CalComCalendar()


def get_booking_use_case() -> BookingUseCase | None:
    try:
        calendar = get_calendar()
        catalog = get_service_catalog()
        store = get_conversation_store()
        tz = ZoneInfo(settings.BUSINESS_TIMEZONE)
        return BookingUseCase(
            calendar=calendar,
            catalog=catalog,
            store=store,
            timezone=tz,
            buffer_minutes=settings.BOOKING_BUFFER_MINUTES,
        )
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.warning("Booking use case not available", extra={"error": str(e)})
        return None


def get_instagram_platform() -> InstagramPlatform:
    logger = logging.getLogger(__name__)
    logger.info(
        "META_PAGE_ACCESS_TOKEN present=%s len=%s",
        bool(settings.META_PAGE_ACCESS_TOKEN),
        len(settings.META_PAGE_ACCESS_TOKEN or ""),
    )
    logger.info("ENV=%s", settings.ENV)

    if not settings.META_PAGE_ACCESS_TOKEN:
        if settings.ENV.lower() in {"dev", "local"}:
            logger.info("Using MockInstagramPlatform (token missing, ENV=dev/local)")
            return MockInstagramPlatform()
        raise ValueError("META_PAGE_ACCESS_TOKEN is required to send Instagram replies.")

    logger.info("Using real InstagramPlatform")
    client = InstagramClient(
        access_token=settings.META_PAGE_ACCESS_TOKEN,
        send_endpoint=settings.META_INSTAGRAM_SEND_ENDPOINT,
    )
    return InstagramPlatform(client=client)


def get_handle_incoming_message_use_case() -> HandleIncomingMessageUseCase:
    return HandleIncomingMessageUseCase(
        store=get_conversation_store(),
        kb=get_knowledge_base(),
        classify_intent=ClassifyIntentUseCase(llm=get_llm()),
        generate_reply=GenerateReplyUseCase(kb=get_knowledge_base()),
        send_reply=SendReplyUseCase(platform=get_instagram_platform()),
        booking_use_case=get_booking_use_case(),
        service_catalog=get_service_catalog(),
        business_name=settings.BUSINESS_NAME,
        business_tone=settings.BUSINESS_TONE,
        auto_reply_enabled=settings.AUTO_REPLY_ENABLED,
    )


def get_container() -> dict[str, object]:
    return {
        "use_case": get_handle_incoming_message_use_case(),
        "store": get_conversation_store(),
    }
