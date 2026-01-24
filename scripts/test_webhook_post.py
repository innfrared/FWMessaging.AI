#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import time
from typing import Any

import httpx
from httpx import ConnectError


def build_payload(sender_id: str, recipient_id: str, text: str) -> dict[str, Any]:
    now_ms = int(time.time() * 1000)
    return {
        "object": "instagram",
        "entry": [
            {
                "id": recipient_id,
                "time": now_ms,
                "messaging": [
                    {
                        "sender": {"id": sender_id},
                        "recipient": {"id": recipient_id},
                        "timestamp": now_ms,
                        "message": {"mid": f"m_{now_ms}", "text": text},
                    }
                ],
            }
        ],
    }


def sign_body(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a test Instagram webhook POST")
    parser.add_argument("--url", default="http://127.0.0.1:8001/webhooks/instagram")
    parser.add_argument("--sender", default="user_123")
    parser.add_argument("--recipient", default="page_456")
    parser.add_argument("--text", default="What are your prices?")
    parser.add_argument("--app-secret", default="", help="Meta app secret for signature")
    args = parser.parse_args()

    payload = build_payload(args.sender, args.recipient, args.text)
    body = json.dumps(payload).encode("utf-8")

    headers = {"Content-Type": "application/json"}
    if args.app_secret:
        headers["X-Hub-Signature-256"] = sign_body(args.app_secret, body)

    try:
        resp = httpx.post(args.url, content=body, headers=headers, timeout=10.0)
    except ConnectError:
        print("Connection refused. Is the FastAPI server running?")
        print("Try: uvicorn app.main:app --reload --port 8001")
        return

    print(resp.status_code)
    if resp.text:
        print(resp.text)


if __name__ == "__main__":
    main()
