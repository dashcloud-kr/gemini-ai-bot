"""Gemini API 클라이언트 (Google AI Studio 무료 티어)."""

from __future__ import annotations

import base64
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-flash-latest"


class GeminiError(RuntimeError):
    """Gemini API 오류."""


class RateLimitError(GeminiError):
    """무료 티어 한도 초과 (429)."""


class GeminiClient:
    def __init__(
        self,
        http: httpx.AsyncClient,
        api_key: str,
        model: str = DEFAULT_MODEL,
    ) -> None:
        self._http = http
        self._api_key = api_key
        self._model = model

    async def _post(self, body: dict[str, Any]) -> str:
        response = await self._http.post(
            f"{BASE_URL}/models/{self._model}:generateContent",
            params={"key": self._api_key},
            json=body,
        )
        if response.status_code == 429:
            raise RateLimitError("무료 한도를 초과했습니다")
        if response.status_code == 402:
            raise GeminiError(
                "Gemini 크레딧이 부족합니다. "
                "AI Studio(ai.studio/projects)에서 프로젝트·결제를 확인하세요."
            )
        if response.status_code >= 400:
            message = "알 수 없는 오류"
            try:
                payload = response.json()
                message = payload.get("error", {}).get("message", message)
            except ValueError:
                pass
            raise GeminiError(f"Gemini 오류 {response.status_code}: {message}")

        payload = response.json()
        candidates = payload.get("candidates", [])
        if not candidates:
            feedback = payload.get("promptFeedback", {})
            reason = feedback.get("blockReason")
            if reason:
                raise GeminiError(f"응답이 차단되었습니다 ({reason})")
            raise GeminiError("응답이 비어 있습니다")

        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(str(part.get("text", "")) for part in parts).strip()
        if not text:
            raise GeminiError("응답 텍스트가 비어 있습니다")
        return text

    async def generate(
        self,
        history: list[tuple[str, str]],
        user_message: str,
        system_prompt: str | None = None,
    ) -> str:
        """history: [(role, content)] — role 은 user/model."""
        contents: list[dict[str, Any]] = [
            {"role": role, "parts": [{"text": content}]} for role, content in history
        ]
        contents.append({"role": "user", "parts": [{"text": user_message}]})

        body: dict[str, Any] = {"contents": contents}
        if system_prompt:
            body["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        return await self._post(body)

    async def describe_image(
        self,
        image_bytes: bytes,
        mime_type: str,
        prompt: str,
    ) -> str:
        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": base64.b64encode(image_bytes).decode("ascii"),
                            }
                        },
                    ],
                }
            ]
        }
        return await self._post(body)
