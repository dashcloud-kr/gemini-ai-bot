"""Gemini 클라이언트 테스트 (respx 모킹)."""

from __future__ import annotations

import base64

import httpx
import pytest
import respx

from app.clients.gemini import BASE_URL, DEFAULT_MODEL, GeminiClient, GeminiError, RateLimitError

GENERATE_URL = f"{BASE_URL}/models/{DEFAULT_MODEL}:generateContent"


def payload(text: str = "안녕하세요!") -> dict:
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


@pytest.fixture
def http():
    return httpx.AsyncClient()


@respx.mock
async def test_응답_파싱(http):
    route = respx.post(GENERATE_URL).mock(return_value=httpx.Response(200, json=payload()))
    client = GeminiClient(http, "test-key")
    answer = await client.generate([], "안녕")

    assert answer == "안녕하세요!"
    request = route.calls[0].request
    assert request.url.params["key"] == "test-key"


@respx.mock
async def test_여러_파트_합치기(http):
    body = {"candidates": [{"content": {"parts": [{"text": "안녕"}, {"text": "하세요"}]}}]}
    respx.post(GENERATE_URL).mock(return_value=httpx.Response(200, json=body))
    client = GeminiClient(http, "test-key")
    assert await client.generate([], "hi") == "안녕하세요"


@respx.mock
async def test_대화기록과_시스템프롬프트_전달(http):
    import json

    route = respx.post(GENERATE_URL).mock(return_value=httpx.Response(200, json=payload()))
    client = GeminiClient(http, "test-key")
    await client.generate(
        [("user", "이전 질문"), ("model", "이전 답변")],
        "새 질문",
        "너는 비서야",
    )

    body = json.loads(route.calls[0].request.content)
    assert body["contents"][0] == {"role": "user", "parts": [{"text": "이전 질문"}]}
    assert body["contents"][1] == {"role": "model", "parts": [{"text": "이전 답변"}]}
    assert body["contents"][2] == {"role": "user", "parts": [{"text": "새 질문"}]}
    assert body["systemInstruction"]["parts"][0]["text"] == "너는 비서야"


@respx.mock
async def test_429는_전용_예외(http):
    respx.post(GENERATE_URL).mock(return_value=httpx.Response(429, json={}))
    client = GeminiClient(http, "test-key")
    with pytest.raises(RateLimitError):
        await client.generate([], "hi")


@respx.mock
async def test_오류_메시지_전달(http):
    respx.post(GENERATE_URL).mock(
        return_value=httpx.Response(400, json={"error": {"message": "API key not valid"}})
    )
    client = GeminiClient(http, "bad")
    with pytest.raises(GeminiError, match="API key not valid"):
        await client.generate([], "hi")


@respx.mock
async def test_차단된_응답(http):
    respx.post(GENERATE_URL).mock(
        return_value=httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}})
    )
    client = GeminiClient(http, "test-key")
    with pytest.raises(GeminiError, match="차단"):
        await client.generate([], "hi")


@respx.mock
async def test_빈_응답(http):
    respx.post(GENERATE_URL).mock(
        return_value=httpx.Response(200, json={"candidates": [{"content": {"parts": []}}]})
    )
    client = GeminiClient(http, "test-key")
    with pytest.raises(GeminiError):
        await client.generate([], "hi")


@respx.mock
async def test_이미지_전송(http):
    import json

    route = respx.post(GENERATE_URL).mock(
        return_value=httpx.Response(200, json=payload("강아지네요"))
    )
    client = GeminiClient(http, "test-key")
    answer = await client.describe_image(b"\xff\xd8fake", "image/jpeg", "뭐야?")

    assert answer == "강아지네요"
    body = json.loads(route.calls[0].request.content)
    parts = body["contents"][0]["parts"]
    assert parts[0]["text"] == "뭐야?"
    assert parts[1]["inline_data"]["mime_type"] == "image/jpeg"
    assert base64.b64decode(parts[1]["inline_data"]["data"]) == b"\xff\xd8fake"
