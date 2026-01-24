from __future__ import annotations

from openai import OpenAI

from app.application.exceptions import LLMUpstreamError


class OpenAIClient:
    def __init__(self, api_key: str) -> None:
        self._client = OpenAI(api_key=api_key)

    def chat_text(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        try:
            resp = self._client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            raise LLMUpstreamError(f"OpenAI API error: {exc}") from exc

        content = (resp.choices[0].message.content or "").strip() if resp.choices else ""
        return content

    def chat_json(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        try:
            resp = self._client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            raise LLMUpstreamError(f"OpenAI API error: {exc}") from exc

        content = (resp.choices[0].message.content or "").strip() if resp.choices else ""
        return content
