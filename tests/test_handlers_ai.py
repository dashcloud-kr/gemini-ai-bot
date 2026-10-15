"""AI 핸들러 테스트 (스텁 Gemini 사용)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.clients.gemini import GeminiError, RateLimitError
from app.handlers import ai
from tests.factories import make_context, make_message_update, make_photo_update


class StubGemini:
    def __init__(self, reply: str = "네, 안녕하세요!", error: Exception | None = None) -> None:
        self.reply = reply
        self.error = error
        self.calls: list[tuple] = []

    async def generate(self, history, user_message, system_prompt=None):
        self.calls.append((history, user_message, system_prompt))
        if self.error is not None:
            raise self.error
        return self.reply

    async def describe_image(self, image_bytes, mime_type, prompt):
        self.calls.append(("image", image_bytes, mime_type, prompt))
        if self.error is not None:
            raise self.error
        return "강아지 사진이네요"


def _ctx(update, repo, gemini=None, username: str = "test_bot"):
    message = update.effective_message
    args = message.text.split()[1:] if message is not None and message.text else []
    ctx = make_context(
        args=args,
        bot_data={"repo": repo, "gemini": gemini or StubGemini()},
    )
    ctx.bot.username = username
    update.get_bot().username = username
    return ctx


def _texts(update) -> list[str]:
    return [call.kwargs["text"] for call in update.get_bot().send_message.await_args_list]


def _last(update) -> str:
    return _texts(update)[-1]


MENTION = [{"type": "mention", "offset": 0, "length": 9}]  # "@test_bot"


# ---- 개인 채팅 대화 ---------------------------------------------------------


async def test_개인_메시지_응답과_기록(repo):
    gemini = StubGemini()
    update = make_message_update("안녕")
    ctx = _ctx(update, repo, gemini)

    await ai.on_text(update, ctx)

    assert "안녕하세요" in _last(update)
    assert gemini.calls[0][1] == "안녕"
    history = await repo.recent_history(100, 100)
    assert history == [("user", "안녕"), ("model", "네, 안녕하세요!")]
    assert await repo.get_usage(100, ai._today()) == 1


async def test_대화_기억이_전달됨(repo):
    gemini = StubGemini()
    ctx = _ctx(make_message_update("첫 질문"), repo, gemini)
    await ai.on_text(make_message_update("첫 질문"), ctx)

    update2 = make_message_update("두 번째 질문")
    await ai.on_text(update2, ctx)

    history = gemini.calls[1][0]
    assert ("user", "첫 질문") in history
    assert ("model", "네, 안녕하세요!") in history


async def test_사용량_한도(repo):
    for _ in range(ai.DAILY_LIMIT):
        await repo.increment_usage(100, ai._today())

    gemini = StubGemini()
    update = make_message_update("안녕")
    await ai.on_text(update, _ctx(update, repo, gemini))

    assert "모두 썼습니다" in _last(update)
    assert gemini.calls == []


async def test_Gemini_오류_안내(repo):
    gemini = StubGemini(error=RateLimitError("429"))
    update = make_message_update("안녕")
    await ai.on_text(update, _ctx(update, repo, gemini))
    assert "무료 사용량" in _last(update)

    gemini = StubGemini(error=GeminiError("boom"))
    update = make_message_update("안녕")
    await ai.on_text(update, _ctx(update, repo, gemini))
    assert "실패" in _last(update)


# ---- 그룹방 ----------------------------------------------------------------


async def test_그룹_멘션없으면_무응답(repo):
    gemini = StubGemini()
    update = make_message_update("안녕", chat_type="group")
    await ai.on_text(update, _ctx(update, repo, gemini))

    assert _texts(update) == []
    assert gemini.calls == []
    assert await repo.get_usage(100, ai._today()) == 0


async def test_그룹_멘션하면_응답하고_멘션_제거(repo):
    gemini = StubGemini()
    update = make_message_update(
        "@test_bot 안녕", chat_type="group", entities=MENTION
    )
    await ai.on_text(update, _ctx(update, repo, gemini))

    assert gemini.calls[0][1] == "안녕"  # 멘션 제거됨
    assert len(_texts(update)) == 1


async def test_그룹_봇_메시지에_답장하면_응답(repo):
    gemini = StubGemini()
    reply_to = {
        "message_id": 9,
        "date": 1760000000,
        "chat": {"id": 100, "type": "group"},
        "from": {"id": 999, "is_bot": True, "first_name": "AI"},
        "text": "이전 답변",
    }
    update = make_message_update(
        "그럼 이건?", chat_type="group", reply_to=reply_to
    )
    await ai.on_text(update, _ctx(update, repo, gemini))
    assert len(_texts(update)) == 1


# ---- 명령어 ----------------------------------------------------------------


async def test_reset(repo):
    await repo.add_message(100, 100, "user", "A", "t")
    update = make_message_update("/reset")
    await ai.cmd_reset(update, _ctx(update, repo))
    assert "초기화" in _last(update)
    assert await repo.recent_history(100, 100) == []


async def test_persona_설정_조회_해제(repo):
    update = make_message_update("/persona")
    await ai.cmd_persona(update, _ctx(update, repo))
    assert "설정 없음" in _last(update)

    update = make_message_update("/persona 너는 친절한 비서야")
    await ai.cmd_persona(update, _ctx(update, repo))
    assert await repo.get_persona(100, 100) == "너는 친절한 비서야"

    # 페르소나가 다음 요청에 전달됨
    gemini = StubGemini()
    update = make_message_update("안녕")
    await ai.on_text(update, _ctx(update, repo, gemini))
    assert gemini.calls[0][2] == "너는 친절한 비서야"

    update = make_message_update("/persona off")
    await ai.cmd_persona(update, _ctx(update, repo))
    assert await repo.get_persona(100, 100) is None


async def test_usage_명령어(repo):
    update = make_message_update("/usage")
    await ai.cmd_usage(update, _ctx(update, repo))
    assert "0/30회" in _last(update)

    await repo.increment_usage(100, ai._today())
    update = make_message_update("/usage")
    await ai.cmd_usage(update, _ctx(update, repo))
    assert "1/30회" in _last(update)


# ---- 사진 ------------------------------------------------------------------


def _photo_ctx(update, repo, gemini):
    ctx = _ctx(update, repo, gemini)
    ctx.bot.username = "test_bot"
    update.get_bot().username = "test_bot"

    async def fake_download(buffer):
        buffer.write(b"fake-image-bytes")

    ctx.bot.get_file = AsyncMock(
        return_value=SimpleNamespace(download_to_memory=fake_download)
    )
    return ctx


async def test_사진_분석(repo):
    gemini = StubGemini()
    update = make_photo_update("이거 뭐야?")
    await ai.on_photo(update, _photo_ctx(update, repo, gemini))

    assert "강아지" in _last(update)
    call = gemini.calls[0]
    assert call[0] == "image"
    assert call[1] == b"fake-image-bytes"
    assert call[3] == "이거 뭐야?"


async def test_사진_기본_프롬프트(repo):
    gemini = StubGemini()
    update = make_photo_update()
    await ai.on_photo(update, _photo_ctx(update, repo, gemini))
    assert gemini.calls[0][3] == ai.DEFAULT_IMAGE_PROMPT


async def test_사진_그룹_멘션없으면_무응답(repo):
    gemini = StubGemini()
    update = make_photo_update(chat_type="group")
    await ai.on_photo(update, _photo_ctx(update, repo, gemini))
    assert gemini.calls == []
