from __future__ import annotations

import logging

import httpx


class InstagramClient:
    def __init__(self, access_token: str, send_endpoint: str) -> None:
        self._access_token = access_token
        self._send_endpoint = send_endpoint
        self._client = httpx.Client(timeout=10.0)
        self._logger = logging.getLogger(__name__)

    def send_text(self, recipient_id: str, text: str) -> None:
        payload = {
            "recipient": {"id": recipient_id},
            "message": {"text": text},
        }
        params = {"access_token": self._access_token}
        resp = self._client.post(self._send_endpoint, params=params, json=payload)
        if resp.status_code >= 400:
            error_body = resp.text
            try:
                error_json = resp.json()
                error_code = error_json.get("error", {}).get("code")
                error_message = error_json.get("error", {}).get("message")
                error_subcode = error_json.get("error", {}).get("error_subcode")
            except Exception:
                error_code = None
                error_message = error_body
                error_subcode = None

            self._logger.error(
                "Instagram send failed",
                extra={
                    "status": resp.status_code,
                    "error_code": error_code,
                    "error_message": error_message,
                    "error_subcode": error_subcode,
                    "recipient_id": recipient_id,
                    "text_length": len(text),
                },
            )
            resp.raise_for_status()
