from __future__ import annotations

import hmac
import logging
from typing import Mapping


logger = logging.getLogger(__name__)


def verify_get_request(params: Mapping[str, str], expected_token: str) -> str | None:
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    if mode == "subscribe" and token and token == expected_token:
        return challenge
    return None


def verify_post_signature(body: bytes, signature_header: str | None, app_secret: str | None, env: str) -> bool:
    if not signature_header:
        if env.lower() in {"dev", "local"}:
            logger.warning("Missing signature header; accepting in dev mode")
            return True
        return False

    if not app_secret:
        logger.error("Missing app secret for signature verification")
        return False

    try:
        algo, signature = signature_header.split("=", 1)
    except ValueError:
        return False

    if algo.lower() != "sha256":
        return False

    expected = hmac.new(app_secret.encode("utf-8"), body, "sha256").hexdigest()
    return hmac.compare_digest(expected, signature)
