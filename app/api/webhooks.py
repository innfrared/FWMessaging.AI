from __future__ import annotations

import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse

from app.application.dto.webhook_event import WebhookEventDTO
from app.infrastructure.instagram.webhook_verify import verify_post_signature
from app.wiring.dependencies import get_handle_incoming_message_use_case
from app.core.config import settings


router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/webhooks/instagram")
def verify_webhook(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.META_VERIFY_TOKEN:
        return PlainTextResponse(hub_challenge or "")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhooks/instagram")
async def instagram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> Response:
    try:
        try:
            use_case = get_handle_incoming_message_use_case()
        except Exception as e:
            logger.exception("Failed to initialize use case", extra={"error": str(e)})
            return Response(status_code=500)

        body = await request.body()
        signature = request.headers.get("X-Hub-Signature-256")
        if not verify_post_signature(body, signature, settings.META_APP_SECRET, settings.ENV):
            return Response(status_code=403)

        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            logger.exception("Failed to parse webhook body")
            return Response(status_code=400)

        try:
            event = WebhookEventDTO.model_validate(payload)
            messages = event.extract_messages()

            logger.info("Webhook received", extra={"message_count": len(messages)})

            for message in messages:
                background_tasks.add_task(use_case.handle, message)

            return Response(status_code=200)
        except Exception as e:
            logger.exception("Error processing webhook event", extra={"error": str(e)})
            return Response(status_code=500)
    except Exception as e:
        logger.exception("Fatal error in webhook handler", extra={"error": str(e)})
        return Response(status_code=500)
